#!/bin/bash
# unassemble.sh — split files too large for GitHub into committable pieces.
#
# GitHub refuses files over 100 MB.  This script finds every file over 100 MB
# under the directory it lives in (skipping .git and existing pieces), splits
# each one F into 90 MB pieces F.part-aa, F.part-ab, ... (split -b 90m), and
# adds F to .gitignore, so that only the pieces are committed.  A file whose
# pieces git would ignore anyway (it sits in a directory .gitignore keeps out,
# such as OldVersions/FourPackage/wcnf/) is skipped.
# reassemble.sh puts the files back together.
#
# Running it again is harmless: a file whose pieces are all newer than it and
# add up to exactly its length is reported as already split and left alone.
# When the file is newer than its pieces (it changed, or reassemble.sh just
# rebuilt it) the pieces are compared with it byte for byte: if they match,
# it is already split; if not, its old pieces are removed and it is split
# again.
#
# Usage: ./unassemble.sh          (from anywhere; works on the CLARA checkout)
#
# Written for bash 3.2 (macOS /bin/bash) as well as newer bash.

here=$(cd "$(dirname "$0")" && pwd -P) || exit 1
ignore=$here/.gitignore
piece=90m

split_count=0 current=0 ignored=0 skipped=0 failed=0
while IFS= read -r -d '' whole; do
    rel=${whole#"$here"/}

    # a file in a place .gitignore keeps out on purpose (e.g. a whole
    # ignored directory) would have its pieces ignored too: leave it alone
    if git -C "$here" check-ignore -q -- "$rel.part-aa"; then
        echo "skipped (git ignores its location): $rel"
        skipped=$((skipped + 1))
        continue
    fi

    size=$(wc -c < "$whole") || { failed=$((failed + 1)); continue; }

    # already split?  pieces exist and add up to the file's length, and either
    # all are newer than the file or (as after reassemble.sh, which leaves the
    # file newer) their contents are the file's
    up_to_date=no
    if [ -f "$whole.part-aa" ]; then
        total=0
        pieces_newer=yes
        for p in "$whole".part-*; do
            total=$((total + $(wc -c < "$p")))
            if [ ! "$p" -nt "$whole" ]; then
                pieces_newer=no
            fi
        done
        if [ "$total" -eq "$size" ]; then
            if [ "$pieces_newer" = yes ]; then
                up_to_date=yes
            elif cat "$whole".part-* | cmp -s - "$whole"; then
                up_to_date=yes
            fi
        fi
    fi

    if [ "$up_to_date" = yes ]; then
        echo "already split: $rel"
        current=$((current + 1))
    else
        echo "splitting: $rel ($((size / 1048576)) MB)"
        rm -f "$whole".part-*          # old pieces, which may be more than the new ones
        if split -b "$piece" "$whole" "$whole.part-"; then
            total=0
            for p in "$whole".part-*; do
                total=$((total + $(wc -c < "$p")))
            done
            if [ "$total" -eq "$size" ]; then
                split_count=$((split_count + 1))
            else
                echo "  FAILED: the pieces of $rel do not add up to its length" >&2
                rm -f "$whole".part-*
                failed=$((failed + 1))
                continue
            fi
        else
            echo "  FAILED: could not split $rel" >&2
            rm -f "$whole".part-*
            failed=$((failed + 1))
            continue
        fi
    fi

    # keep the whole file out of git
    if ! grep -qxF "$rel" "$ignore" 2>/dev/null; then
        # make sure .gitignore ends with a newline before appending
        if [ -s "$ignore" ] && [ -n "$(tail -c 1 "$ignore")" ]; then
            echo >> "$ignore"
        fi
        echo "$rel" >> "$ignore"
        echo "  added to .gitignore: $rel"
        ignored=$((ignored + 1))
    fi
    if git -C "$here" ls-files --error-unmatch -- "$rel" > /dev/null 2>&1; then
        echo "  WARNING: $rel is tracked by git; .gitignore does not untrack it." >&2
        echo "           Run: git -C \"$here\" rm --cached -- \"$rel\"" >&2
    fi
done < <(find "$here" -name .git -prune -o -type f -size +100M ! -name '*.part-*' -print0 | sort -z)

echo "$split_count split, $current already split, $ignored added to .gitignore, $skipped skipped, $failed failed"
[ "$failed" -eq 0 ]
