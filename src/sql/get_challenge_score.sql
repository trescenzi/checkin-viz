CREATE 
or REPLACE FUNCTION get_challenge_score(challenge_id_input INTEGER, knocked_out_input BOOLEAN) 
returns table(
  points numeric,
  name text,
  tier text
) 
language plpgsql as $$ 
BEGIN
   RETURN Query 
   SELECT
      SUM(q.count),
      q.name,
      q.tier 
   FROM
      (
         SELECT
            subq.week,
            subq.name,
            subq.tier,
            LEAST(subq.count, 5) as count 
         FROM
            (
               SELECT
                  date_part('week', c.time at time zone 'America/New_York') as week,
                  c.name,
                  cc.tier as tier,
                  COUNT(distinct date_part('day', c.time at time zone 'America/New_York')) as count 
               FROM
                  checkins c 
                  join
                     challenge_weeks cw 
                     on c.challenge_week_id = cw.id 
                     and cw.challenge_id = challenge_id_input 
                  join
                     challenger_challenges cc 
                     on c.challenger = cc.challenger_id 
                     and cc.challenge_id = challenge_id_input 
               WHERE
                  cc.knocked_out = knocked_out_input
                  AND cc.ante > 0 
                  and cc.tier != 'T0' 
               GROUP BY
                  week,
                  c.name,
                  cc.tier 
               ORDER BY
                  week DESC,
                  c.name,
                  cc.tier 
            )
            as subq
      )
      as q 
   group by
      q.name,
      q.tier 
   order by
      q.tier;
end
;
$$ ;
