#!/bin/bash
# reassemble.sh — rejoin the files that were committed in pieces.
#
# GitHub refuses files over 100 MB, so each larger file F (so far, d4
# circuits F.dnnf) is committed as 90 MB pieces F.part-aa, F.part-ab, ...
# (made by unassemble.sh, with split -b 90m), and F itself is in .gitignore.
# This script finds every such set of pieces under the directory it lives in
# and writes F from them.
#
# For each F, with the rule unassemble.sh shares:
#   F missing                                  -> built from the pieces
#   no piece newer than F, same total length   -> "already reassembled"
#   a piece newer than F (e.g. after git pull) -> rebuilt from the pieces
#   F newer than every piece, different length -> F was changed here since it
#                                                 was split: LEFT ALONE, with a
#                                                 warning (run unassemble.sh to
#                                                 split it again, or delete it
#                                                 to rebuild it from the pieces)
# So running it again is harmless.
#
# Usage: ./reassemble.sh          (from anywhere; works on the CLARA checkout)
#
# Written for bash 3.2 (macOS /bin/bash) as well as newer bash.

here=$(cd "$(dirname "$0")" && pwd -P) || exit 1

# an interrupted run must not leave a partial file behind
tmp=""
trap '[ -n "$tmp" ] && rm -f "$tmp"' EXIT
trap 'exit 130' INT TERM HUP

built=0 current=0 kept=0 failed=0
while IFS= read -r -d '' first; do
    whole=${first%.part-aa}
    rel=${whole#"$here"/}
    parts=("$whole".part-*)

    total=0
    pieces_newer=no
    for p in "${parts[@]}"; do
        size=$(wc -c < "$p") || { failed=$((failed + 1)); continue 2; }
        total=$((total + size))
        if [ -f "$whole" ] && [ "$p" -nt "$whole" ]; then
            pieces_newer=yes
        fi
    done

    if [ -f "$whole" ] && [ "$pieces_newer" = no ]; then
        if [ "$(wc -c < "$whole")" -eq "$total" ]; then
            echo "already reassembled: $rel"
            current=$((current + 1))
        else
            echo "KEPT: $rel is newer than its pieces and differs from them (changed here" >&2
            echo "      since it was split?).  Left alone: run ./unassemble.sh to split it" >&2
            echo "      again, or delete it to rebuild it from the pieces." >&2
            kept=$((kept + 1))
        fi
        continue
    fi

    echo "reassembling: $rel (${#parts[@]} pieces)"
    tmp=$whole.reassemble-tmp
    if cat "${parts[@]}" > "$tmp" && [ "$(wc -c < "$tmp")" -eq "$total" ] \
            && mv -f "$tmp" "$whole"; then
        built=$((built + 1))
    else
        echo "  FAILED: $rel" >&2
        rm -f "$tmp"
        failed=$((failed + 1))
    fi
    tmp=""
done < <(find "$here" -name .git -prune -o -name '*.part-aa' -type f -print0 | sort -z)

echo "$built reassembled, $current already up to date, $kept kept (changed here), $failed failed"
[ "$failed" -eq 0 ]
