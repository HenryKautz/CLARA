;; Per-hypothesis posterior from the saved H=5 circuit, without recompiling:
;; P(h|T) and P(h|T,O) by clamping the assertion literal (OBSDONE 1 3 5), then
;; normalise P(h|T,O)/P(h|T) (uniform priors).  Prints the numbers in
;; results/crosscheck-intrusion-obs3-h5.txt.
;;
;; Usage, from AAAI-2010-Benchmarks/ (FiFO installed; or load a checkout's lisp/):
;;   sbcl --noinform --non-interactive \
;;        --eval '(load "~/lib/fifo/lisp/FiFO.lisp")' --eval '(load "~/lib/fifo/lisp/ddnnf.lisp")' \
;;        --load circuits/query-h5-circuit.lisp
;; It reads the binary circuit when present (fast) and otherwise the text one.
;; The binary .dnnfb is git-ignored; regenerate both files with
;;   marginals.sh theories/IntrusionDetectionCosts-obs3-H5.scnf --solver d4 \
;;                --save-circuit circuits/IntrusionDetectionCosts-obs3-H5.dnnf
(let* ((here (directory-namestring (or *load-truename* *default-pathname-defaults*)))
       (bin (concatenate 'string here "IntrusionDetectionCosts-obs3-H5.dnnfb"))
       (c (ddnnf-load (if (probe-file bin) bin
                          (concatenate 'string here "IntrusionDetectionCosts-obs3-H5.dnnf"))))
       (u (ddnnf-marginals nil :circuit c :verbose nil))
       (o (ddnnf-marginals nil :circuit c :verbose nil :evidence (list '(obsdone 1 3 5))))
       (hyps (loop for i below 10 collect (list 'holds (list (intern (format nil "HYP~D" i))) 5)))
       (r (mapcar (lambda (h)
                    (let ((pu (cdr (assoc h u :test #'equal)))
                          (po (cdr (assoc h o :test #'equal))))
                      (if (> pu 0) (/ po pu) 0d0)))
                  hyps))
       (z (reduce #'+ r)))
  (loop for h in hyps for x in r
        do (format t "~S ~,6F~%" (second h) (/ x z))))
