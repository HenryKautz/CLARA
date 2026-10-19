;; grid5x5-4-pkg2-p1-5
;; Single-goal variant of grid5x5-4.pddl: the goal is (at pkg2 p1-5) only.
;; 5 x 5 grid of places, roads between adjacent cells;
;; no airports;
;; 1 truck and 2 packages placed at random, 0 airplanes over the airports.
;; 2 destinations per package; reaching any one of them counts.
;; At least one of the 2 packages must reach a destination.
;;

(define (problem grid5x5-4-pkg2-p1-5)
  (:domain clara-logistics)

  (:objects
        p1-1 p1-2 p1-3 p1-4 p1-5 p2-1 p2-2 p2-3 p2-4 p2-5 p3-1 p3-2 p3-3 p3-4 p3-5 p4-1 p4-2 p4-3 p4-4 p4-5 p5-1 p5-2 p5-3 p5-4 p5-5 - place
        truck1 - truck
        pkg1 pkg2 - package)

  (:init
        ;; where everything starts
        (at pkg1 p5-4)
        (at pkg2 p2-1)
        (at truck1 p3-5)

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


        ;; travel prices: one value for every drive, one for every flight
        (= (total-cost) 0)
        (= (drive-cost) 1)
        (= (fly-cost) 3))

  (:goal (and
        (at pkg2 p1-5)))

  (:metric minimize (total-cost)))
