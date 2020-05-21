FLUSH TABLES WITH READ LOCK; SET GLOBAL read_only = ON;
SELECT "serverlevel" INTO OUTFILE "/var/lib/mysql-files/azbackupserver.txt";
SLEEP(900);