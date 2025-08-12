ALTER TABLE IF EXISTS `journal` DROP FOREIGN KEY IF EXISTS `fk_journal_publisher`;
ALTER TABLE IF EXISTS `link` DROP FOREIGN KEY IF EXISTS `fk_link_publisher`;
ALTER TABLE IF EXISTS `excelfilehistory` DROP FOREIGN KEY IF EXISTS `fk_excelfilehistory_publisher`;

DROP TABLE IF EXISTS `publisher`;
DROP TABLE IF EXISTS `journal`;
DROP TABLE IF EXISTS `excelfilehistory`;
DROP TABLE IF EXISTS `link`;
DROP TABLE IF EXISTS `session`;
DROP TABLE IF EXISTS `session_h`;
DROP TABLE IF EXISTS `geoip`;
DROP TABLE IF EXISTS `setting`;

