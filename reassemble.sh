#!/bin/bash
# reassemble.sh — rejoin the files that were committed in pieces.
#
# GitHub refuses files over 100 MB, so each larger file F (so far, d4
# circuits F.dnnf) is committed as 90 MB pieces F.part-aa, F.part-ab, ...
# (made by unassemble.sh, with split -b 90m), and F itself is in .gitignore.
# This script finds every such set of pieces under the directory it lives in
# and writes F from them.
#
# Running it again is harmless: a file that is newer than all its pieces and
# exactly as long as they are together is reported as already reassembled
# and left alone.  If the pieces change (say, after a git pull), they are
# newer than the file, so it is rebuilt.
#
# Usage: ./reassemble.sh          (from anywhere; works on the CLARA checkout)
#
# Written for bash 3.2 (macOS /bin/bash) as well as newer bash.

here=$(cd "$(dirname "$0")" && pwd -P) || exit 1

built=0 current=0 failed=0
while IFS= read -r -d '' first; do
    whole=${first%.part-aa}
    rel=${whole#"$here"/}
    parts=("$whole".part-*)

    # total length of the pieces, and is the whole file newer than every piece?
    total=0
    newer=yes
    for p in "${parts[@]}"; do
        size=$(wc -c < "$p") || { failed=$((failed + 1)); continue 2; }
        total=$((total + size))
        if [ ! "$whole" -nt "$p" ]; then
            newer=no
        fi
    done

    if [ -f "$whole" ] && [ "$newer" = yes ] && [ "$(wc -c < "$whole")" -eq "$total" ]; then
        echo "already reassembled: $rel"
        current=$((current + 1))
        continue
    fi

    # write to a temporary name first, so an interrupted run never leaves a
    # truncated file that looks newer than its pieces
    echo "reassembling: $rel (${#parts[@]} pieces)"
    if cat "${parts[@]}" > "$whole.tmp" && [ "$(wc -c < "$whole.tmp")" -eq "$total" ] \
            && mv -f "$whole.tmp" "$whole"; then
        built=$((built + 1))
    else
        echo "  FAILED: $rel" >&2
        rm -f "$whole.tmp"
        failed=$((failed + 1))
    fi
done < <(find "$here" -name .git -prune -o -name '*.part-aa' -type f -print0 | sort -z)

echo "$built reassembled, $current already up to date, $failed failed"
[ "$failed" -eq 0 ]
