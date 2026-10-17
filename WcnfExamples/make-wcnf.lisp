;;; make-wcnf.lisp -- write one SimpleGrid problem's weighted CNF, with and without
;;; evidence, in both dialects, plus its variable map.  Called by make-examples.sh:
;;;   sbcl --eval '(load FiFO.lisp)' --eval '(load wmc.lisp)' \
;;;        --eval '(defparameter *job* (list SCNF BASE EVIDENCE-FILE))' --load make-wcnf.lisp
;;; writes BASE-2020.wcnf, BASE-2024.wcnf, BASE-ev2-2020.wcnf, BASE-ev2-2024.wcnf
;;; and BASE.map ("<var> <atom>" per line), using FiFO's own writer (the same
;;; preamble as wmc-write-wcnf: theory clauses + the evidence clauses, atoms
;;; numbered by mx--index-atoms, wmc--write-mcc in each dialect).  Errors unless
;;; the evidence variant numbers every atom the same way, so one map serves all four.

(destructuring-bind (scnf base evfile) *job*
  (multiple-value-bind (clauses probs opts weight-forms) (rw--read-scnf scnf)
    (declare (ignore probs opts))
    (let* ((weight-atoms (mapcar (lambda (wf) (rw--literal-atom-and-sign (second wf)))
                                 weight-forms))
           (scale (rw--resolve-scale scnf nil nil))
           (maps '()))
      (dolist (variant (list (cons "" nil) (cons "-ev2" evfile)))
        (let* ((ev (wmc--evidence-clauses nil (cdr variant) clauses))
               (all (append clauses ev)))
          (when (and (cdr variant) (null ev))
            (error "evidence file ~A gave no clauses" (cdr variant)))
          (multiple-value-bind (a2i nvars) (mx--index-atoms all weight-atoms)
            (dolist (d '((:mcc-2020 . "-2020") (:mcc-2024 . "-2024")))
              (with-open-file (s (format nil "~A~A~A.wcnf" base (car variant) (cdr d))
                                 :direction :output :if-exists :supersede)
                (wmc--write-mcc all weight-forms a2i nvars s :scale scale :dialect (car d))))
            (let ((m (make-array (1+ nvars))))
              (maphash (lambda (atom v) (setf (aref m v) atom)) a2i)
              (push m maps))
            (format t "~&~A~A: ~D vars, ~D clauses (~D evidence)~%"
                    base (car variant) nvars (length all) (length ev)))))
      (unless (equalp (first maps) (second maps))
        (error "the evidence variant numbers the atoms differently"))
      (with-open-file (s (format nil "~A.map" base) :direction :output :if-exists :supersede)
        (let ((*print-pretty* nil))
          (loop for v from 1 below (length (first maps))
                do (format s "~D ~S~%" v (aref (first maps) v))))))))
