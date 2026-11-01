;; grid5x5-1: the recognition problem
;; grid5x5-1.pddl with its goal -- one destination for each package -- written
;; as the disjunction of its 8 combinations (the same set of plans).
;; recognize.sh scores disjunct I through the derived atom rechypI:
;;   rechyp0  (at pkg1 p2-4) (at pkg2 p3-4) (at pkg3 p4-3)   shortest horizon 16
;;   rechyp1  (at pkg1 p2-4) (at pkg2 p3-4) (at pkg3 p5-4)   shortest horizon 16
;;   rechyp2  (at pkg1 p2-4) (at pkg2 p2-4) (at pkg3 p4-3)   shortest horizon 13
;;   rechyp3  (at pkg1 p2-4) (at pkg2 p2-4) (at pkg3 p5-4)   shortest horizon 15
;;   rechyp4  (at pkg1 p4-4) (at pkg2 p3-4) (at pkg3 p4-3)   shortest horizon 18
;;   rechyp5  (at pkg1 p4-4) (at pkg2 p3-4) (at pkg3 p5-4)   shortest horizon 17
;;   rechyp6  (at pkg1 p4-4) (at pkg2 p2-4) (at pkg3 p4-3)   shortest horizon 17
;;   rechyp7  (at pkg1 p4-4) (at pkg2 p2-4) (at pkg3 p5-4)   shortest horizon 16
;; Recognition horizon: 18
;;   (the largest shortest horizon: every combination is achievable at it)
;; Written by scripts/plan-goals.py.

(define (problem grid5x5-1)
  (:domain clara-logistics-handling)

  (:objects
        p1-1 p1-2 p1-3 p1-4 p1-5 p2-1 p2-2 p2-3 p2-4 p2-5 p3-1 p3-2 p3-3 p3-4 p3-5 p4-1 p4-2 p4-3 p4-4 p4-5 p5-1 p5-2 p5-3 p5-4 p5-5 - place
        truck1 - truck
        pkg1 pkg2 pkg3 - package)

  (:init
        ;; where everything starts
        (at pkg1 p3-2)
        (at pkg2 p3-3)
        (at pkg3 p2-4)
        (at truck1 p2-1)

        ;; static topology: roads within each road network,
        ;; routes between every pair of airports
        (road p2-1 p1-1)
        (road p1-1 p2-1)
        (road p1-2 p1-1)
        (road p1-1 p1-2)
        (road p2-3 p1-3)
        (road p1-3 p2-3)
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
        (road p2-5 p2-4)
        (road p2-4 p2-5)
        (road p3-5 p2-5)
        (road p2-5 p3-5)
        (road p4-1 p3-1)
        (road p3-1 p4-1)
        (road p3-2 p3-1)
        (road p3-1 p3-2)
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
        (road p5-4 p4-4)
        (road p4-4 p5-4)
        (road p4-5 p4-4)
        (road p4-4 p4-5)
        (road p5-5 p4-5)
        (road p4-5 p5-5)
        (road p5-4 p5-3)
        (road p5-3 p5-4)
        (road p5-5 p5-4)
        (road p5-4 p5-5)


        ;; travel prices: one value for every drive, one for every flight
        (= (total-cost) 0)
        (= (drive-cost) 2)
        (= (fly-cost) 3))

  (:goal (or
        (and (at pkg1 p2-4) (at pkg2 p3-4) (at pkg3 p4-3))
        (and (at pkg1 p2-4) (at pkg2 p3-4) (at pkg3 p5-4))
        (and (at pkg1 p2-4) (at pkg2 p2-4) (at pkg3 p4-3))
        (and (at pkg1 p2-4) (at pkg2 p2-4) (at pkg3 p5-4))
        (and (at pkg1 p4-4) (at pkg2 p3-4) (at pkg3 p4-3))
        (and (at pkg1 p4-4) (at pkg2 p3-4) (at pkg3 p5-4))
        (and (at pkg1 p4-4) (at pkg2 p2-4) (at pkg3 p4-3))
        (and (at pkg1 p4-4) (at pkg2 p2-4) (at pkg3 p5-4))))

  (:metric minimize (total-cost)))
