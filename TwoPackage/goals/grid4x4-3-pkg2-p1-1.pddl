;; grid4x4-3-pkg2-p1-1
;; Single-goal variant of grid4x4-3.pddl: the goal is (at pkg2 p1-1) only.
;; 4 x 4 grid of places, roads between adjacent cells;
;; no airports;
;; 1 truck and 2 packages placed at random, 0 airplanes over the airports.
;; 2 destinations per package; reaching any one of them counts.
;; At least one of the 2 packages must reach a destination.
;;

(define (problem grid4x4-3-pkg2-p1-1)
  (:domain clara-logistics-old)

  (:objects
        p1-1 p1-2 p1-3 p1-4 p2-1 p2-2 p2-3 p2-4 p3-1 p3-2 p3-3 p3-4 p4-1 p4-2 p4-3 p4-4 - place
        truck1 - truck
        pkg1 pkg2 - package)

  (:init
        ;; where everything starts
        (at pkg1 p3-1)
        (at pkg2 p3-2)
        (at truck1 p3-3)

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


        ;; travel prices: one value for every drive, one for every flight
        (= (total-cost) 0)
        (= (drive-cost) 1)
        (= (fly-cost) 3))

  (:goal (and
        (at pkg2 p1-1)))

  (:metric minimize (total-cost)))
