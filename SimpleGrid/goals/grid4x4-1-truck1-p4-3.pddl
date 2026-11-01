;; grid4x4-1-truck1-p4-3
;; Single-goal variant of SimpleGrid/grid4x4-1.pddl: the hard goal is
;; (at truck1 p4-3) -- hypothesis at-truck1-p4-3 of the recognition problem.
;; No preferences or weights.  Written by scripts/make-problems.py.

(define (problem grid4x4-1-truck1-p4-3)
  (:domain clara-logistics)

  (:objects
        p1-1 p1-2 p1-3 p1-4 p2-1 p2-2 p2-3 p2-4 p3-1 p3-2 p3-3 p3-4 p4-1 p4-2 p4-3 p4-4 - place
        truck1 - truck)

  (:init
        ;; where everything starts
        (at truck1 p1-1)

        ;; static topology: roads within each road network,
        ;; routes between every pair of airports
        (road p2-1 p1-1)
        (road p1-1 p2-1)
        (road p1-2 p1-1)
        (road p1-1 p1-2)
        (road p2-2 p1-2)
        (road p1-2 p2-2)
        (road p1-3 p1-2)
        (road p1-2 p1-3)
        (road p2-3 p1-3)
        (road p1-3 p2-3)
        (road p1-4 p1-3)
        (road p1-3 p1-4)
        (road p2-4 p1-4)
        (road p1-4 p2-4)
        (road p3-1 p2-1)
        (road p2-1 p3-1)
        (road p2-2 p2-1)
        (road p2-1 p2-2)
        (road p3-2 p2-2)
        (road p2-2 p3-2)
        (road p2-3 p2-2)
        (road p2-2 p2-3)
        (road p3-3 p2-3)
        (road p2-3 p3-3)
        (road p2-4 p2-3)
        (road p2-3 p2-4)
        (road p3-4 p2-4)
        (road p2-4 p3-4)
        (road p4-1 p3-1)
        (road p3-1 p4-1)
        (road p3-2 p3-1)
        (road p3-1 p3-2)
        (road p4-2 p3-2)
        (road p3-2 p4-2)
        (road p3-3 p3-2)
        (road p3-2 p3-3)
        (road p4-3 p3-3)
        (road p3-3 p4-3)
        (road p3-4 p3-3)
        (road p3-3 p3-4)
        (road p4-4 p3-4)
        (road p3-4 p4-4)
        (road p4-2 p4-1)
        (road p4-1 p4-2)
        (road p4-3 p4-2)
        (road p4-2 p4-3)
        (road p4-4 p4-3)
        (road p4-3 p4-4)


        ;; prices: one value for every drive, one for every flight, one for
        ;; every load or unload
        (= (total-cost) 0)
        (= (drive-cost) 1)
        (= (fly-cost) 3)
        (= (handle-cost) 1))

  (:goal (at truck1 p4-3))

  (:metric minimize (total-cost)))
