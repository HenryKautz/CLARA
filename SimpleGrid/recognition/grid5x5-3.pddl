;; grid5x5-3: the recognition problem
;; SimpleGrid/grid5x5-3.pddl with its goal written as ONE disjunction of its
;; 4 hypotheses (the same set of plans).  recognize.sh's names:
;;   at-truck1-p5-4   (at truck1 p5-4)   shortest horizon 8
;;   at-truck1-p4-5   (at truck1 p4-5)   shortest horizon 8
;;   at-truck1-p5-5   (at truck1 p5-5)   shortest horizon 9
;;   at-truck1-p5-3   (at truck1 p5-3)   shortest horizon 7
;; Recognition horizon: 9
;;   (the largest shortest horizon: every hypothesis is achievable at it)
;; Written by scripts/plan-goals.py.

(define (problem grid5x5-3)
  (:domain clara-logistics)

  (:objects
        p1-1 p1-2 p1-3 p1-4 p1-5 p2-1 p2-2 p2-3 p2-4 p2-5 p3-1 p3-2 p3-3 p3-4 p3-5 p4-1 p4-2 p4-3 p4-4 p4-5 p5-1 p5-2 p5-3 p5-4 p5-5 - place
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
        (road p1-5 p1-4)
        (road p1-4 p1-5)
        (road p2-5 p1-5)
        (road p1-5 p2-5)
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
        (road p2-5 p2-4)
        (road p2-4 p2-5)
        (road p3-5 p2-5)
        (road p2-5 p3-5)
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
        (road p3-5 p3-4)
        (road p3-4 p3-5)
        (road p4-5 p3-5)
        (road p3-5 p4-5)
        (road p5-1 p4-1)
        (road p4-1 p5-1)
        (road p4-2 p4-1)
        (road p4-1 p4-2)
        (road p5-2 p4-2)
        (road p4-2 p5-2)
        (road p4-3 p4-2)
        (road p4-2 p4-3)
        (road p5-3 p4-3)
        (road p4-3 p5-3)
        (road p4-4 p4-3)
        (road p4-3 p4-4)
        (road p5-4 p4-4)
        (road p4-4 p5-4)
        (road p4-5 p4-4)
        (road p4-4 p4-5)
        (road p5-5 p4-5)
        (road p4-5 p5-5)
        (road p5-2 p5-1)
        (road p5-1 p5-2)
        (road p5-3 p5-2)
        (road p5-2 p5-3)
        (road p5-4 p5-3)
        (road p5-3 p5-4)
        (road p5-5 p5-4)
        (road p5-4 p5-5)


        ;; prices: one value for every drive, one for every flight, one for
        ;; every load or unload
        (= (total-cost) 0)
        (= (drive-cost) 1)
        (= (fly-cost) 3)
        (= (handle-cost) 1))

  (:goal (or
        (at truck1 p5-4)
        (at truck1 p4-5)
        (at truck1 p5-5)
        (at truck1 p5-3)))

  (:metric minimize (total-cost)))
