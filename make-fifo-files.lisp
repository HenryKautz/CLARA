;;; make-fifo-files.lisp -- the Lisp half of make-fifo-files.py.
;;;
;;; Loaded after FiFO.lisp, maxent.lisp, wmc.lisp, pddl2fifo.lisp and planner.lisp.
;;; Three entry points, each printing one result line make-fifo-files.py reads:
;;;
;;;   (cf-write-wcnf SCNF BASE &key evidence-forms evtag)
;;;       BASE-2020.wcnf and BASE-2024.wcnf -- SCNF's weighted CNF in the MCC 2020
;;;       (ADDMC) and MCC 2024 (SharpSAT-TD) dialects -- and BASE.map, variable
;;;       number -> FiFO atom.  With EVIDENCE-FORMS, also BASE<EVTAG>-2020.wcnf and
;;;       BASE<EVTAG>-2024.wcnf, the theory plus those forms' clauses; it is an
;;;       error unless both number every atom the same way, so one map serves all.
;;;       FiFO's own writer, as in wmc-write-wcnf: theory clauses (+ evidence),
;;;       atoms numbered by mx--index-atoms, wmc--write-mcc in each dialect.
;;;
;;;   (cf-pddl-wff PROBLEM DOMAIN EVFILE)
;;;       Translate PROBLEM with pddl2fifo, registering the PDDL evidence in EVFILE
;;;       (one (occur-in-order ...)) exactly as planner.sh --pddl-evidence-file
;;;       does, and append the evidence's observation-monitor AXIOMS to the wff as
;;;       a FiFO formula -- what planner.sh --split-evidence folds into the scnf.
;;;       The wff is written beside PROBLEM; its include names "satplan.wff".
;;;
;;;   (cf-check-wff WFF SCNF OUT)
;;;       Instantiate WFF into OUT and compare its clauses with SCNF's as a
;;;       MULTISET of forms, comment lines aside: a CNF is a set of clauses, and
;;;       for the AAAI theories the order does differ -- the planner appends the
;;;       monitor axioms after the problem's clauses, while instantiating the wff
;;;       emits them first.  Prints WFF-CHECK OK (same order too), WFF-CHECK
;;;       OK-REORDERED, or WFF-CHECK MISMATCH, with the two clause counts.

(defun cf--clauses (file)
  "Every form in the scnf FILE (comment lines are skipped by READ)."
  (with-open-file (in file)
    (let ((*read-eval* nil))
      (loop for f = (read in nil :eof) until (eq f :eof) collect f))))

(defun cf-write-wcnf (scnf base &key evidence-forms (evtag "-ev"))
  (multiple-value-bind (clauses probs opts weight-forms) (rw--read-scnf scnf)
    (declare (ignore probs opts))
    (let* ((weight-atoms (mapcar (lambda (wf) (rw--literal-atom-and-sign (second wf)))
                                 weight-forms))
           (scale (rw--resolve-scale scnf nil nil))
           (maps '()))
      (dolist (variant (cons (cons "" nil) (when evidence-forms (list (cons evtag evidence-forms)))))
        (let* ((ev (and (cdr variant) (wmc--evidence-clauses (cdr variant) nil clauses)))
               (all (append clauses ev)))
          (when (and (cdr variant) (null ev))
            (error "the evidence gave no clauses: ~S" (cdr variant)))
          (multiple-value-bind (a2i nvars) (mx--index-atoms all weight-atoms)
            (dolist (d '((:mcc-2020 . "-2020") (:mcc-2024 . "-2024")))
              (with-open-file (s (format nil "~A~A~A.wcnf" base (car variant) (cdr d))
                                 :direction :output :if-exists :supersede)
                (wmc--write-mcc all weight-forms a2i nvars s :scale scale :dialect (car d))))
            (let ((m (make-array (1+ nvars))))
              (maphash (lambda (atom v) (setf (aref m v) atom)) a2i)
              (push m maps))
            (format t "~&WCNF ~A~A ~D ~D~%" (file-namestring base) (car variant)
                    nvars (length all)))))
      (when (and (second maps) (not (equalp (first maps) (second maps))))
        (error "the evidence variant numbers the atoms differently"))
      (with-open-file (s (format nil "~A.map" base) :direction :output :if-exists :supersede)
        (let ((*print-pretty* nil))
          (loop for v from 1 below (length (first maps))
                do (format s "~D ~S~%" v (aref (first maps) v))))))))

(defun cf-pddl-wff (problem domain evfile)
  (let* ((forms (plan--evidence-forms nil evfile)))
    (multiple-value-bind (wff rmin ev-fifo)
        (pddl2fifo problem :domain-file domain :satplan-path "satplan.wff"
                           :pddl-evidence forms)
      (declare (ignore rmin))
      (multiple-value-bind (axioms assertion) (plan--split-evidence ev-fifo)
        (unless assertion
          (error "~A is not one (occur-in-order ...): nothing to split" evfile))
        (with-open-file (s wff :direction :output :if-exists :append)
          (format s "~%;; Observation-monitor axioms for the evidence in ~A:~%~
                     ;; determined and count-neutral, so they condition on nothing.~%~
                     ;; planner.sh --split-evidence folds them into the theory; the~%~
                     ;; literal to condition on is in the scnf's -assertion.txt.~%"
                  (file-namestring evfile))
          (let ((*print-pretty* t) (*print-right-margin* 100) (*print-case* :downcase))
            (format s "~S~%" axioms)))
        (format t "~&PDDL-WFF ~A~%" wff)))))

(defun cf-check-wff (wff scnf out)
  (unless (instantiate wff :scnfile out)
    (error "instantiating ~A failed" wff))
  (let* ((a (cf--clauses out)) (b (cf--clauses scnf))
         (key (lambda (c) (let ((*print-pretty* nil)) (prin1-to-string c))))
         (verdict (cond ((equal a b) "OK")
                        ((equal (sort (mapcar key a) #'string<) (sort (mapcar key b) #'string<))
                         "OK-REORDERED")
                        (t "MISMATCH"))))
    (format t "~&WFF-CHECK ~A ~D ~D~%" verdict (length a) (length b))))
