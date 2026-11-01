;; grid3x3-3: the recognition problem
;; SimpleGrid/grid3x3-3.pddl with its goal written as ONE disjunction of its
;; 2 hypotheses (the same set of plans).  recognize.sh's names:
;;   at-truck1-p2-3   (at truck1 p2-3)   shortest horizon 4
;;   at-truck1-p3-3   (at truck1 p3-3)   shortest horizon 5
;; Recognition horizon: 5
;;   (the largest shortest horizon: every hypothesis is achievable at it)
;; Written by scripts/plan-goals.py.

(define (problem grid3x3-3)
  (:domain clara-logistics)

  (:objects
        p1-1 p1-2 p1-3 p2-1 p2-2 p2-3 p3-1 p3-2 p3-3 - place
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

  (:goal (or
        (at truck1 p2-3)
        (at truck1 p3-3)))

  (:metric minimize (total-cost)))
