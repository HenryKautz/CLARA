;; grid3x3-4-pkg2-p3-3
;; Single-goal variant of grid3x3-4.pddl: the goal is (at pkg2 p3-3) only.
;; 3 x 3 grid of places, roads between adjacent cells;
;; no airports;
;; 1 truck and 2 packages placed at random, 0 airplanes over the airports.
;; 2 destinations per package; reaching any one of them counts.
;; At least one of the 2 packages must reach a destination.
;;

(define (problem grid3x3-4-pkg2-p3-3)
  (:domain clara-logistics-old)

  (:objects
        p1-1 p1-2 p1-3 p2-1 p2-2 p2-3 p3-1 p3-2 p3-3 - place
        truck1 - truck
        pkg1 pkg2 - package)

  (:init
        ;; where everything starts
        (at pkg1 p2-3)
        (at pkg2 p1-2)
        (at truck1 p3-2)

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


        ;; travel prices: one value for every drive, one for every flight
        (= (total-cost) 0)
        (= (drive-cost) 1)
        (= (fly-cost) 3))

  (:goal (and
        (at pkg2 p3-3)))

  (:metric minimize (total-cost)))
