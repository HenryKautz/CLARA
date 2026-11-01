#!/bin/bash
# unassemble.sh — split files too large for GitHub into committable pieces.
#
# GitHub refuses files over 100 MB.  This script splits every file F over
# 100 MB under the directory it lives in into 90 MB pieces F.part-aa,
# F.part-ab, ... (split -b 90m) and adds F to .gitignore, so that only the
# pieces are committed; reassemble.sh puts F back together.  It also looks at
# every F that already has pieces, whatever its size now.
#
# For each F, with the rule reassemble.sh shares:
#   git ignores F by some other rule (a pattern such as general/*.wcnf, or an
#   ignored directory): it is kept out on purpose -> skipped
#   a piece newer than F (e.g. after git pull): F is the stale copy -> skipped,
#     with a reminder to run reassemble.sh
#   no piece newer than F, same total length -> "already split"
#   F differs from its pieces (changed here):
#     over 100 MB -> its old pieces are replaced by new ones
#     100 MB or less -> its pieces and its .gitignore line are removed, so F
#                       itself is committed
#   no pieces, over 100 MB -> split
# New pieces get F's modification time, so right after a split both scripts
# see F as up to date.  Running it again is harmless.
#
# Usage: ./unassemble.sh          (from anywhere; works on the CLARA checkout)
#
# Written for bash 3.2 (macOS /bin/bash) as well as newer bash.

here=$(cd "$(dirname "$0")" && pwd -P) || exit 1
ignore=$here/.gitignore
limit=104857600          # 100 MB (MiB, as GitHub counts), the same as find's +100M
piece=90m

# an interrupted run must not leave partial pieces behind
cur=""
trap '[ -n "$cur" ] && rm -f "$cur".split-tmp-*' EXIT
trap 'exit 130' INT TERM HUP

# every file over 100 MB, and every file that has pieces, once each
candidates() {
    find "$here" -name .git -prune -o -type f -size +100M ! -name '*.part-*' \
         ! -name '*.split-tmp-*' ! -name '*.reassemble-tmp' -print0
    find "$here" -name .git -prune -o -type f -name '*.part-aa' -print0 |
        while IFS= read -r -d '' p; do printf '%s\0' "${p%.part-aa}"; done
}

add_ignore() {           # add the line $1 to .gitignore unless it is there
    if ! grep -qxF "$1" "$ignore" 2>/dev/null; then
        if [ -s "$ignore" ] && [ -n "$(tail -c 1 "$ignore")" ]; then
            echo >> "$ignore"            # .gitignore lacked a final newline
        fi
        echo "$1" >> "$ignore"
        echo "  added to .gitignore: $1"
        ignored=$((ignored + 1))
    fi
}

drop_ignore() {          # remove the line $1 from .gitignore
    if grep -qxF "$1" "$ignore" 2>/dev/null; then
        grep -vxF "$1" "$ignore" > "$ignore.tmp" && cat "$ignore.tmp" > "$ignore"
        rm -f "$ignore.tmp"
        echo "  removed from .gitignore: $1"
    fi
}

split_count=0 current=0 ignored=0 unsplit=0 skipped=0 failed=0
while IFS= read -r -d '' whole; do
    [ -f "$whole" ] || continue          # pieces only: reassemble.sh's job
    rel=${whole#"$here"/}

    # ignored by a rule other than its own line?  (check-ignore reports the
    # last rule that matches, which is its own line when that is present)
    rule=$(git -C "$here" check-ignore -v -- "$rel" 2>/dev/null)
    if [ -n "$rule" ]; then
        pattern=${rule%%$'\t'*}
        pattern=${pattern#*:}
        pattern=${pattern#*:}
        # a "!pattern" match means NOT ignored
        if [ "${pattern#!}" = "$pattern" ] && [ "$pattern" != "$rel" ] && [ "$pattern" != "/$rel" ]; then
            echo "skipped (git ignores it by '$pattern'): $rel"
            skipped=$((skipped + 1))
            continue
        fi
    fi

    size=$(wc -c < "$whole") || { failed=$((failed + 1)); continue; }

    if [ -f "$whole.part-aa" ]; then
        total=0
        pieces_newer=no
        for p in "$whole".part-*; do
            total=$((total + $(wc -c < "$p")))
            if [ "$p" -nt "$whole" ]; then
                pieces_newer=yes
            fi
        done
        if [ "$pieces_newer" = yes ]; then
            echo "skipped (its pieces are newer; run ./reassemble.sh first): $rel"
            skipped=$((skipped + 1))
            continue
        fi
        if [ "$total" -eq "$size" ]; then
            echo "already split: $rel"
            current=$((current + 1))
            add_ignore "$rel"
            continue
        fi
        if [ "$size" -le "$limit" ]; then
            echo "now 100 MB or less, so no longer split: $rel"
            rm -f "$whole".part-*
            drop_ignore "$rel"
            unsplit=$((unsplit + 1))
            continue
        fi
    fi

    echo "splitting: $rel ($((size / 1048576)) MB)"
    cur=$whole
    if split -b "$piece" "$whole" "$whole.split-tmp-"; then
        total=0
        for p in "$whole".split-tmp-*; do
            total=$((total + $(wc -c < "$p")))
        done
    else
        total=-1
    fi
    if [ "$total" -ne "$size" ]; then
        echo "  FAILED: could not split $rel" >&2
        rm -f "$whole".split-tmp-*
        failed=$((failed + 1))
        cur=""
        continue
    fi
    # the new pieces take F's time (so F is not older than them), then
    # replace the old ones
    touch -r "$whole" "$whole".split-tmp-*
    rm -f "$whole".part-*
    for p in "$whole".split-tmp-*; do
        mv -f "$p" "$whole.part-${p#"$whole".split-tmp-}"
    done
    cur=""
    split_count=$((split_count + 1))
    add_ignore "$rel"

    if git -C "$here" ls-files --error-unmatch -- "$rel" > /dev/null 2>&1; then
        echo "  WARNING: $rel is tracked by git; .gitignore does not untrack it." >&2
        echo "           Run: git -C \"$here\" rm --cached -- \"$rel\"" >&2
    fi
done < <(candidates | sort -zu)

echo "$split_count split, $current already split, $unsplit no longer split," \
     "$ignored added to .gitignore, $skipped skipped, $failed failed"
[ "$failed" -eq 0 ]
