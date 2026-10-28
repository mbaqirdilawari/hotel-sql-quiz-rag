-- Hotel Bookings SQL Quiz: tables and sample data
-- Run this whole file once in the Supabase SQL Editor.

DROP TABLE IF EXISTS bookings;
DROP TABLE IF EXISTS rooms;
DROP TABLE IF EXISTS hotels;

-- Table 1: one row per hotel
CREATE TABLE hotels (
    hotel_id     INTEGER PRIMARY KEY,
    hotel_name   TEXT NOT NULL,
    city         TEXT NOT NULL,
    star_rating  INTEGER NOT NULL CHECK (star_rating BETWEEN 1 AND 5)
);

-- Table 2: one row per room; each room belongs to one hotel
CREATE TABLE rooms (
    room_id        INTEGER PRIMARY KEY,
    hotel_id       INTEGER NOT NULL REFERENCES hotels(hotel_id),
    room_type      TEXT NOT NULL,
    nightly_price  NUMERIC(8,2) NOT NULL
);

-- Table 3: one row per booking; each booking is for one room
CREATE TABLE bookings (
    booking_id     INTEGER PRIMARY KEY,
    room_id        INTEGER NOT NULL REFERENCES rooms(room_id),
    guest_name     TEXT NOT NULL,
    check_in_date  DATE NOT NULL,
    nights         INTEGER NOT NULL CHECK (nights > 0)
);

INSERT INTO hotels (hotel_id, hotel_name, city, star_rating) VALUES
    (1, 'Grand Palace', 'Lahore', 5),
    (2, 'Lakeview Inn', 'Islamabad', 3),
    (3, 'Seaside Resort', 'Karachi', 4),
    (4, 'Mall Road Suites', 'Lahore', 4),
    (5, 'Margalla Heights', 'Islamabad', 5),
    (6, 'Clifton Bay Hotel', 'Karachi', 3),
    (7, 'Old City Guesthouse', 'Lahore', 2),
    (8, 'Hunza Valley Lodge', 'Hunza', 3);

INSERT INTO rooms (room_id, hotel_id, room_type, nightly_price) VALUES
    (101, 1, 'Standard', 120),
    (102, 1, 'Deluxe', 250),
    (103, 1, 'Suite', 450),
    (104, 1, 'Standard', 130),
    (201, 2, 'Standard', 70),
    (202, 2, 'Deluxe', 110),
    (203, 2, 'Standard', 75),
    (301, 3, 'Standard', 95),
    (302, 3, 'Deluxe', 160),
    (303, 3, 'Suite', 300),
    (401, 4, 'Standard', 100),
    (402, 4, 'Deluxe', 180),
    (403, 4, 'Suite', 320),
    (404, 4, 'Deluxe', 190),
    (501, 5, 'Standard', 140),
    (502, 5, 'Deluxe', 260),
    (503, 5, 'Suite', 500),
    (601, 6, 'Standard', 65),
    (602, 6, 'Deluxe', 105),
    (603, 6, 'Standard', 60),
    (701, 7, 'Standard', 40),
    (702, 7, 'Deluxe', 70),
    (801, 8, 'Standard', 85),
    (802, 8, 'Deluxe', 140),
    (803, 8, 'Suite', 220);

INSERT INTO bookings (booking_id, room_id, guest_name, check_in_date, nights) VALUES
    (1, 701, 'Kamran Javed', '2026-09-07', 1),
    (2, 602, 'Mehwish Aslam', '2026-09-16', 2),
    (3, 601, 'Usman Tariq', '2026-09-16', 7),
    (4, 503, 'Fatima Ali', '2026-09-28', 1),
    (5, 102, 'Kamran Javed', '2026-09-29', 1),
    (6, 303, 'Bilal Hussain', '2026-10-02', 2),
    (7, 601, 'Ali Haider', '2026-10-06', 3),
    (8, 803, 'Bilal Hussain', '2026-10-07', 2),
    (9, 201, 'Sara Ahmed', '2026-10-08', 3),
    (10, 801, 'Ahmed Farooq', '2026-10-15', 7),
    (11, 501, 'Raj Patel', '2026-10-16', 2),
    (12, 104, 'John Smith', '2026-10-17', 7),
    (13, 801, 'Ayesha Khan', '2026-10-20', 3),
    (14, 403, 'Fatima Ali', '2026-10-21', 4),
    (15, 404, 'Bilal Hussain', '2026-10-24', 1),
    (16, 503, 'Zara Sheikh', '2026-10-24', 2),
    (17, 202, 'Kamran Javed', '2026-10-28', 3),
    (18, 104, 'Hina Raza', '2026-11-03', 1),
    (19, 702, 'Zara Sheikh', '2026-11-08', 3),
    (20, 103, 'John Smith', '2026-11-10', 3),
    (21, 104, 'Mehwish Aslam', '2026-11-10', 1),
    (22, 102, 'Emily Chen', '2026-11-13', 7),
    (23, 602, 'Ali Haider', '2026-11-13', 2),
    (24, 103, 'Sophie Brown', '2026-11-13', 2),
    (25, 501, 'Ali Haider', '2026-11-14', 4),
    (26, 303, 'Omar Siddiqui', '2026-11-17', 1),
    (27, 102, 'Ahmed Farooq', '2026-11-19', 2),
    (28, 102, 'Kamran Javed', '2026-11-25', 1),
    (29, 801, 'John Smith', '2026-11-25', 1),
    (30, 802, 'Mehwish Aslam', '2026-11-29', 2),
    (31, 602, 'Zara Sheikh', '2026-12-11', 3),
    (32, 602, 'Fatima Ali', '2026-12-12', 4),
    (33, 601, 'Omar Siddiqui', '2026-12-14', 2),
    (34, 702, 'Usman Tariq', '2026-12-15', 4),
    (35, 502, 'Nadia Iqbal', '2026-12-22', 3),
    (36, 302, 'Hamza Malik', '2026-12-23', 2),
    (37, 702, 'Bilal Hussain', '2026-12-23', 3),
    (38, 201, 'Hamza Malik', '2026-12-29', 4),
    (39, 103, 'Ahmed Farooq', '2026-12-30', 2),
    (40, 401, 'Emily Chen', '2026-12-31', 2);

