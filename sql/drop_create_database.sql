DROP DATABASE IF EXISTS oajf;
CREATE DATABASE oajf CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
GRANT ALL privileges ON oajf.* TO 'oajf'@'localhost' IDENTIFIED BY 'oajf';
GRANT ALL privileges ON oajf.* TO 'oajf'@'127.0.0.1' IDENTIFIED BY 'oajf';

