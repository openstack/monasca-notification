import MySQLdb
#todo figure out mysqldb library

class NotificationProcessor(object):
    pass


# This seems to be the key table
#mysql> describe notification_method;
#+------------+---------------------+------+-----+---------+-------+
#| Field      | Type                | Null | Key | Default | Extra |
#+------------+---------------------+------+-----+---------+-------+
#| id         | varchar(36)         | NO   | PRI | NULL    |       |
#| tenant_id  | varchar(36)         | NO   |     | NULL    |       |
#| name       | varchar(250)        | YES  |     | NULL    |       |
#| type       | enum('EMAIL','SMS') | NO   |     | NULL    |       |
#| address    | varchar(100)        | YES  |     | NULL    |       |
#| created_at | datetime            | NO   |     | NULL    |       |
#| updated_at | datetime            | NO   |     | NULL    |       |
#+------------+---------------------+------+-----+---------+-------+

