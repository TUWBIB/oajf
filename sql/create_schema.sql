CREATE TABLE `publisher` (
	`id` INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
	`name` TINYTEXT NOT NULL,
	`validity` TINYTEXT NOT NULL,
	`oa_status` VARCHAR(50) NULL DEFAULT NULL,
	`application_requirement` VARCHAR(50) NULL DEFAULT NULL,
    `funder_info` VARCHAR(1000) NULL DEFAULT NULL,
    `cost_coverage` VARCHAR(1000) NULL DEFAULT NULL,
    `valid_tu` VARCHAR(100) NULL DEFAULT NULL,
    `article_type` VARCHAR(1000) NULL DEFAULT NULL,
    `further_info` VARCHAR(1000) NULL DEFAULT NULL,
    `funder_info_en` VARCHAR(1000) NULL DEFAULT NULL,
    `cost_coverage_en` VARCHAR(1000) NULL DEFAULT NULL,
    `valid_tu_en` VARCHAR(100) NULL DEFAULT NULL,
    `article_type_en` VARCHAR(1000) NULL DEFAULT NULL,
    `further_info_en` VARCHAR(1000) NULL DEFAULT NULL,
    `is_doaj` TINYINT(1) NOT NULL DEFAULT 0,
    `doaj_linked` TINYINT(1) NOT NULL DEFAULT 0,
	 PRIMARY KEY (`id`)
);

CREATE TABLE `link` (
	`id` INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
	`publisher_id` INT(10) UNSIGNED NOT NULL,
	`link` VARCHAR(200) NULL DEFAULT NULL,
	`linktype` VARCHAR(20) NULL DEFAULT NULL,
	`linktext_de` VARCHAR(200) NULL DEFAULT NULL,
	`linktext_en` VARCHAR(200) NULL DEFAULT NULL,
	PRIMARY KEY (`id`),
	INDEX `fk_link_publisher` (`publisher_id`),
	CONSTRAINT `fk_link_publisher` FOREIGN KEY (`publisher_id`) REFERENCES `publisher` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);

CREATE TABLE `journal` (
	`id` INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
	`title` VARCHAR(250) NOT NULL DEFAULT 'Titel nicht vorhanden',
	`print_issn` CHAR(9) NULL DEFAULT NULL,
	`e_issn` CHAR(9) NULL DEFAULT NULL,
	`link` VARCHAR(2048) NULL DEFAULT '#',
    `valid_till` DATE NULL,
	`publisher_id` INT(10) UNSIGNED NOT NULL,
	PRIMARY KEY (`id`),
	INDEX `fk_journal_publisher` (`publisher_id`),
    INDEX `idx_e_issn` (`e_issn`),
    INDEX `idx_print_issn` (`print_issn`),
	CONSTRAINT `fk_journal_publisher` FOREIGN KEY (`publisher_id`) REFERENCES `publisher` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);

CREATE TABLE `excelfilehistory` (
	`id` INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
	`name` TINYTEXT NOT NULL DEFAULT 'Name nicht vorhanden',
	`file` LONGBLOB NOT NULL,
	`uploaded` TIMESTAMP NOT NULL DEFAULT current_timestamp(),
	`valid` DATE NOT NULL,
	`publisher_id` INT(10) UNSIGNED NOT NULL,
	PRIMARY KEY (`id`),
	INDEX `fk_excelfilehistory_publisher` (`publisher_id`),
	CONSTRAINT `fk_excelfilehistory_publisher` FOREIGN KEY (`publisher_id`) REFERENCES `publisher` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);

CREATE TABLE `setting` (
	`id` INT(10) UNSIGNED NOT NULL AUTO_INCREMENT,
	`name` TINYTEXT NOT NULL UNIQUE,
	`value` TEXT NULL DEFAULT '',
	`value_en` TEXT NULL DEFAULT '',
	`value_de` TEXT NULL DEFAULT '',
	PRIMARY KEY (`id`)
);

CREATE TABLE IF NOT EXISTS `session`
(
    `id` MEDIUMINT NOT NULL AUTO_INCREMENT,    
    `session_id` VARCHAR(64),
    `ip_address` TEXT,
    `ip_group` VARCHAR(50) NULL,
    `country_code` CHAR(2) NULL DEFAULT NULL,
    `http_method` TEXT,
    `request_path` TEXT,
    `post_data` TEXT,
    `form_data` TEXT,
    `session_data` TEXT,
    `user_agent` TEXT,
    `last_activity` DATETIME(6),
    `expires` DATETIME(6),
    PRIMARY KEY (`id`),
    CONSTRAINT `uniq_session_id` UNIQUE (`session_id`)
);

CREATE TABLE `session_h` LIKE `session`;
ALTER TABLE `session_h`
    MODIFY COLUMN `id` int(11) NOT NULL,
    DROP PRIMARY KEY,
    DROP CONSTRAINT `uniq_session_id`,
    ADD `action` VARCHAR(8) DEFAULT 'insert' FIRST, 
    ADD `revision` INT(6) DEFAULT 0 NULL AFTER action,
    ADD `dt_datetime` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER revision,
    ADD PRIMARY KEY (`id`,`revision`);

DROP TRIGGER IF EXISTS `session__ai`;
DROP TRIGGER IF EXISTS `session__au`;
DROP TRIGGER IF EXISTS `session__bd`;

CREATE TRIGGER `session__ai` AFTER INSERT ON session 
    FOR EACH ROW
    INSERT INTO `session_h` 
    SELECT 'insert', 1, NOW(), t.* 
    FROM `session` AS t WHERE t.id = NEW.id;

CREATE TRIGGER `session__au` AFTER UPDATE ON session 
    FOR EACH ROW
    INSERT INTO `session_h` 
    SELECT 'update', (SELECT MAX(th.revision)+1 FROM session_h th2 WHERE th.id=th2.id AND th.revision=th2.revision),NOW(), t.* 
    FROM `session` AS t,`session_h` as th WHERE t.id = NEW.id and th.id=t.id;

CREATE TRIGGER `session__bd` BEFORE DELETE ON session 
    FOR EACH ROW
    INSERT INTO `session_h` 
    SELECT 'delete', (SELECT MAX(th.revision)+1 FROM session_h th2 WHERE th.id=th2.id AND th.revision=th2.revision),NOW(), t.* 
    FROM `session` AS t,`session_h` as th WHERE t.id = OLD.id and th.id=t.id;

CREATE TABLE IF NOT EXISTS `geoip`
(
    `id` MEDIUMINT NOT NULL AUTO_INCREMENT,    
    `ip_from` INET4 NOT NULL,
    `ip_to` INET4 NOT NULL,
    `country_code` CHAR(2) NOT NULL,
    PRIMARY KEY (`id`)
);