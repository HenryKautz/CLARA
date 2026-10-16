# Compiled circuits

`gridNxN-k.scnf` is the ground FiFO theory and `gridNxN-k.dnnf` the d4 circuit
compiled from it (projected, no evidence) by `../compile-d4.py`; results are in
`../results/compile-d4.md`.

Circuits over GitHub's 100 MB limit (`grid8x8-2`, `grid8x8-3`, `grid8x8-4`) are
committed as 90 MB pieces made with `split -b 90m`, and the whole files are
git-ignored. To rebuild one:

```sh
cat grid8x8-2.dnnf.part-* > grid8x8-2.dnnf
```
