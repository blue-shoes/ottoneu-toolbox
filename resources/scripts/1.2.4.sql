UPDATE player set "FG MajorLeagueID"='' where "FG MajorLeagueID" is null;
UPDATE player set "FG MinorLeagueID"='' where "FG MinorLeagueID" is null;
CREATE TEMPORARY TABLE TRANSLATION AS
SELECT t2.[index] as OldID, t1.MaxID as NewID
FROM
  (SELECT MAX([index]) as MaxID ,"FG MajorLeagueID","FG MinorLeagueID","Name"
   FROM player
   where not ("FG MajorLeagueID" = '' AND "FG MinorLeagueID" = '')
   GROUP BY "FG MajorLeagueID","FG MinorLeagueID") t1
INNER JOIN
  player t2 on t1."FG MajorLeagueID" = t2."FG MajorLeagueID" AND t1."FG MinorLeagueID" = t2."FG MinorLeagueID";
UPDATE draft_target
SET player_id = T.NewID
FROM TRANSLATION T
where player_id = T.OldID
and T.OldID <> T.NewID;
UPDATE player_projection
SET player_id = T.NewID
FROM TRANSLATION T
where player_id = T.OldID
and T.OldID <> T.NewID;
UPDATE player_value
SET player_id = T.NewID
FROM TRANSLATION T
where player_id = T.OldID
and T.OldID <> T.NewID;
UPDATE roster_spot
SET player_id = T.NewID
FROM TRANSLATION T
where player_id = T.OldID
and T.OldID <> T.NewID;
UPDATE salary_info
SET player_id = T.NewID
FROM TRANSLATION T
where player_id = T.OldID
and T.OldID <> T.NewID;
delete from player where player.[index] not in (select NewID from TRANSLATION) and not ("FG MajorLeagueID" = '' and "FG MinorLeagueID" = '');
drop table TRANSLATION;

