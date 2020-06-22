FLUSH TABLES WITH READ LOCK; SET GLOBAL read_only = ON;
set @query = concat("SELECT \"serverlevel\" INTO OUTFILE ",@outfile);
prepare stmt from @query;
execute stmt;deallocate prepare stmt;
SELECT SLEEP(@timeout);