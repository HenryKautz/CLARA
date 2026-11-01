;; grid3x3-1-pkg1-p1-3
;; Single-goal variant of TwoPackageOneway/grid3x3-1.pddl: the hard goal is
;; (at pkg1 p1-3) -- hypothesis at-pkg1-p1-3 of the recognition problem.
;; No preferences or weights.  Written by scripts/make-problems.py.

(define (problem grid3x3-1-pkg1-p1-3)
  (:domain clara-logistics)

  (:objects
        p1-1 p1-2 p1-3 p2-1 p2-2 p2-3 p3-1 p3-2 p3-3 - place
        truck1 - truck
        pkg1 pkg2 - package)

  (:init
        ;; where everything starts
        (at pkg1 p3-3)
        (at pkg2 p2-3)
        (at truck1 p2-3)

        ;; static topology: roads within each road network,
        ;; routes between every pair of airports
        (road p2-1 p1-1)
        (road p1-1 p2-1)
        (road p1-2 p1-1)
        (road p1-1 p1-2)
        (road p1-2 p2-2)
        (road p1-3 p1-2)
        (road p2-3 p1-3)
        (road p1-3 p2-3)
        (road p3-1 p2-1)
        (road p2-2 p2-1)
        (road p2-1 p2-2)
        (road p3-2 p2-2)
        (road p2-2 p3-2)
        (road p2-3 p2-2)
        (road p2-2 p2-3)
        (road p3-3 p2-3)
        (road p2-3 p3-3)
        (road p3-2 p3-1)
        (road p3-1 p3-2)
        (road p3-3 p3-2)
        (road p3-2 p3-3)


        ;; prices: one value for every drive, one for every flight, one for
        ;; every load or unload
        (= (total-cost) 0)
        (= (drive-cost) 1)
        (= (fly-cost) 3)
        (= (handle-cost) 1))

  (:goal (at pkg1 p1-3))

  (:metric minimize (total-cost)))
