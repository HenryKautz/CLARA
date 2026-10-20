# Compiled circuits

`gridNxN-k.dnnf` is the d4 circuit compiled (projected, no evidence) by
`../compile-d4.py` from the ground FiFO theory `../scnf/gridNxN-k.scnf` (here
until 2026-10-20); results are in `../results/compile-d4.md`.

Circuits over GitHub's 100 MB limit (`grid8x8-2`, `grid8x8-3`, `grid8x8-4`, and
all four 9×9 circuits, 0.6–1.1 GB each) are
committed as 90 MB pieces made with `split -b 90m`, and the whole files are
git-ignored. To rebuild one:

```sh
cat grid8x8-2.dnnf.part-* > grid8x8-2.dnnf
```
