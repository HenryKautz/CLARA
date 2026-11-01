;; grid4x4-3-p4-4
;; Single-goal variant of grid4x4-3.pddl: the goal is (at truck1 p4-4) only.
;; 4 x 4 grid of places, roads between adjacent cells;
;; no airports;
;; 1 truck at the origin p1-1, 0 airplanes over the airports.
;; No packages: the goal sends each truck to a destination.
;; Every destination is at least 5 steps from the origin by road (3 places qualify).
;;

(define (problem grid4x4-3-p4-4)
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


        ;; travel prices: one value for every drive, one for every flight
        (= (total-cost) 0)
        (= (drive-cost) 1)
        (= (fly-cost) 3))

  (:goal (and
        (at truck1 p4-4)))

  (:metric minimize (total-cost)))
