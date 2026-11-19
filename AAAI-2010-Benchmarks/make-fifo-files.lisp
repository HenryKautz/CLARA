;;; make-fifo-files.lisp -- the Lisp half of make-fifo-files.py.
;;;
;;; Loaded after FiFO.lisp, maxent.lisp, wmc.lisp, pddl2fifo.lisp and planner.lisp.
;;; FiFO's own functions do the work -- wmc-write-wcnf (with :map-file) writes the
;;; weighted CNFs, wmc--read-forms reads scnf files -- so the archive is written
;;; exactly as FiFO writes it, not by a copy that could drift.  Each entry point
;;; prints result lines make-fifo-files.py reads and ends with "DONE"; an error
;;; anywhere exits non-zero (make-fifo-files.py wraps each call in cf-run).
;;;
;;;   (cf-write-wcnf SCNF BASE &key evidence-forms evtag)
;;;       BASE-2020.wcnf and BASE-2024.wcnf -- SCNF's weighted CNF in the MCC 2020
;;;       (ADDMC) and MCC 2024 (SharpSAT-TD) dialects -- and BASE.map, variable
;;;       number -> FiFO atom.  With EVIDENCE-FORMS, also BASE<EVTAG>-2020.wcnf and
;;;       BASE<EVTAG>-2024.wcnf, the theory plus those forms' clauses; an error
;;;       unless their numbering is BASE.map's, so one map serves all four.
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

(defmacro cf-run (&body body)
  "Run BODY; print DONE on success, or the error and exit 1."
  `(handler-case (progn ,@body (format t "~&DONE~%") (finish-output))
     (error (e) (format t "~&ERROR: ~A~%" e) (finish-output) (sb-ext:exit :code 1))))

(defun cf-write-wcnf (scnf base &key evidence-forms (evtag "-ev"))
  (let ((map (format nil "~A.map" base)))
    (dolist (d '((:mcc-2020 . "-2020") (:mcc-2024 . "-2024")))
      (multiple-value-bind (out nvars nclauses)
          (wmc-write-wcnf scnf (format nil "~A~A.wcnf" base (cdr d))
                          :dialect (car d) :map-file map :verbose nil)
        (declare (ignore out))
        (when (eq (car d) :mcc-2024)
          (format t "~&WCNF ~A ~D ~D~%" (file-namestring base) nvars nclauses))))
    (when evidence-forms
      (let ((evmap (format nil "~A~A.map" base evtag)))
        (dolist (d '((:mcc-2020 . "-2020") (:mcc-2024 . "-2024")))
          (multiple-value-bind (out nvars nclauses)
              (wmc-write-wcnf scnf (format nil "~A~A~A.wcnf" base evtag (cdr d))
                              :dialect (car d) :evidence evidence-forms :map-file evmap
                              :verbose nil)
            (declare (ignore out))
            (when (eq (car d) :mcc-2024)
              (format t "~&WCNF ~A~A ~D ~D~%" (file-namestring base) evtag nvars nclauses))))
        (unless (equal (uiop:read-file-string map) (uiop:read-file-string evmap))
          (error "the evidence variant numbers the atoms differently from ~A" map))
        (delete-file evmap)))))

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
  (let* ((a (wmc--read-forms out)) (b (wmc--read-forms scnf))
         (key (lambda (c) (let ((*print-pretty* nil)) (prin1-to-string c))))
         (verdict (cond ((equal a b) "OK")
                        ((equal (sort (mapcar key a) #'string<) (sort (mapcar key b) #'string<))
                         "OK-REORDERED")
                        (t "MISMATCH"))))
    (format t "~&WFF-CHECK ~A ~D ~D~%" verdict (length a) (length b))))
