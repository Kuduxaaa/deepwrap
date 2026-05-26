from deepwrap import Client

BEARER_TOKEN = "YOUR_TOKEN"

client = Client(api_key = BEARER_TOKEN)
chat   = client.chats.create_session(model = "expert")

for kind, chunk in chat.respond_structured(
    "Explain black holes simply.",
    thinking = True,
    search   = True,
):
    if kind == "think":
        print(f"[THINK] {chunk}", end = "", flush = True)

    elif kind == "response":
        print(f"[RESPONSE] {chunk}", end = "", flush = True)

print()

# [THINK] We[THINK]  need[THINK]  to[THINK]  explain[THINK]  black[THINK]  holes[THINK]  simply[THINK] .[THINK]  The[THINK]  user[THINK]  said[THINK] :[THINK]  "[THINK] Explain[THINK]  black[THINK]  holes[THINK]  simply[THINK] ."[THINK]  No[THINK]  other[THINK]  constraints[THINK] .[THINK]  I[THINK]  should[THINK]  provide[THINK]  a[THINK]  clear[THINK] ,[THINK]  straightforward[THINK]  explanation[THINK]  that[THINK] 's[THINK]  easy[THINK]  to[THINK]  understand[THINK] ,[THINK]  avoiding[THINK]  jargon[THINK] .[THINK]  Maybe[THINK]  use[THINK]  an[THINK]  analogy[THINK] .[THINK]  I[THINK] 'll[THINK]  structure[THINK]  it[THINK] :[THINK]  what[THINK]  is[THINK]  a[THINK]  black[THINK]  hole[THINK] ,[THINK]  how[THINK]  it[THINK]  forms[THINK] ,[THINK]  key[THINK]  features[THINK]  ([THINK] event[THINK]  horizon[THINK] ,[THINK]  singularity[THINK] ),[THINK]  and[THINK]  note[THINK]  that[THINK]  they[THINK]  don[THINK] 't[THINK]  "[THINK] s[THINK] uck[THINK] "[THINK]  like[THINK]  a[THINK]  vacuum[THINK] .[THINK]  Keep[THINK]  it[THINK]  friendly[THINK] .[RESPONSE] A[RESPONSE]  black[RESPONSE]  hole[RESPONSE]  is[RESPONSE]  a[RESPONSE]  place[RESPONSE]  in[RESPONSE]  space[RESPONSE]  where[RESPONSE]  gravity[RESPONSE]  is[RESPONSE]  so[RESPONSE]  incredibly[RESPONSE]  strong[RESPONSE]  that[RESPONSE]  nothing[RESPONSE] —[RESPONSE] not[RESPONSE]  even[RESPONSE]  light[RESPONSE] —[RESPONSE] can[RESPONSE]  escape[RESPONSE] .

# [RESPONSE] Imagine[RESPONSE]  a[RESPONSE]  star[RESPONSE]  at[RESPONSE]  least[RESPONSE]  many[RESPONSE]  times[RESPONSE]  more[RESPONSE]  massive[RESPONSE]  than[RESPONSE]  our[RESPONSE]  Sun[RESPONSE] .[RESPONSE]  Stars[RESPONSE]  are[RESPONSE]  a[RESPONSE]  balancing[RESPONSE]  act[RESPONSE] :[RESPONSE]  the[RESPONSE]  energy[RESPONSE]  from[RESPONSE]  nuclear[RESPONSE]  fusion[RESPONSE]  pushes[RESPONSE]  outward[RESPONSE] ,[RESPONSE]  while[RESPONSE]  gravity[RESPONSE]  pulls[RESPONSE]  inward[RESPONSE] .[RESPONSE]  When[RESPONSE]  a[RESPONSE]  massive[RESPONSE]  star[RESPONSE]  runs[RESPONSE]  out[RESPONSE]  of[RESPONSE]  fuel[RESPONSE] ,[RESPONSE]  the[RESPONSE]  outward[RESPONSE]  push[RESPONSE]  stops[RESPONSE] ,[RESPONSE]  and[RESPONSE]  gravity[RESPONSE]  wins[RESPONSE] .[RESPONSE]  The[RESPONSE]  star[RESPONSE]  collapses[RESPONSE]  in[RESPONSE]  on[RESPONSE]  itself[RESPONSE] ,[RESPONSE]  crushing[RESPONSE]  its[RESPONSE]  core[RESPONSE]  into[RESPONSE]  a[RESPONSE]  tiny[RESPONSE]  point[RESPONSE] .[RESPONSE]  This[RESPONSE]  creates[RESPONSE]  a[RESPONSE]  black[RESPONSE]  hole[RESPONSE] .

# [RESPONSE] The[RESPONSE]  “[RESPONSE] surface[RESPONSE] ”[RESPONSE]  of[RESPONSE]  a[RESPONSE]  black[RESPONSE]  hole[RESPONSE]  is[RESPONSE]  called[RESPONSE]  the[RESPONSE]  **[RESPONSE] event[RESPONSE]  horizon[RESPONSE] **.[RESPONSE]  It[RESPONSE] ’[RESPONSE] s[RESPONSE]  not[RESPONSE]  a[RESPONSE]  solid[RESPONSE]  surface[RESPONSE]  you[RESPONSE]  could[RESPONSE]  stand[RESPONSE]  on[RESPONSE] —[RESPONSE] it[RESPONSE] ’[RESPONSE] s[RESPONSE]  the[RESPONSE]  point[RESPONSE]  of[RESPONSE]  no[RESPONSE]  return[RESPONSE] .[RESPONSE]  Once[RESPONSE]  something[RESPONSE]  crosses[RESPONSE]  this[RESPONSE]  boundary[RESPONSE] ,[RESPONSE]  it[RESPONSE] ’[RESPONSE] s[RESPONSE]  gone[RESPONSE]  forever[RESPONSE] .

# [RESPONSE] At[RESPONSE]  the[RESPONSE]  very[RESPONSE]  center[RESPONSE]  lies[RESPONSE]  the[RESPONSE]  **[RESPONSE] singular[RESPONSE] ity[RESPONSE] **,[RESPONSE]  where[RESPONSE]  all[RESPONSE]  the[RESPONSE]  star[RESPONSE] ’[RESPONSE] s[RESPONSE]  mass[RESPONSE]  is[RESPONSE]  crushed[RESPONSE]  into[RESPONSE]  an[RESPONSE]  infinitely[RESPONSE]  small[RESPONSE]  point[RESPONSE]  and[RESPONSE]  our[RESPONSE]  usual[RESPONSE]  laws[RESPONSE]  of[RESPONSE]  physics[RESPONSE]  break[RESPONSE]  down[RESPONSE] .

# [RESPONSE] A[RESPONSE]  common[RESPONSE]  misconception[RESPONSE]  is[RESPONSE]  that[RESPONSE]  black[RESPONSE]  holes[RESPONSE]  act[RESPONSE]  like[RESPONSE]  cosmic[RESPONSE]  vacuum[RESPONSE]  cleaners[RESPONSE] ,[RESPONSE]  sucking[RESPONSE]  everything[RESPONSE]  in[RESPONSE] .[RESPONSE]  But[RESPONSE]  from[RESPONSE]  a[RESPONSE]  distance[RESPONSE] ,[RESPONSE]  a[RESPONSE]  black[RESPONSE]  hole[RESPONSE] ’[RESPONSE] s[RESPONSE]  gravity[RESPONSE]  works[RESPONSE]  just[RESPONSE]  like[RESPONSE]  any[RESPONSE]  other[RESPONSE]  object[RESPONSE]  of[RESPONSE]  the[RESPONSE]  same[RESPONSE]  mass[RESPONSE] .[RESPONSE]  If[RESPONSE]  the[RESPONSE]  Sun[RESPONSE]  were[RESPONSE]  replaced[RESPONSE]  by[RESPONSE]  a[RESPONSE]  black[RESPONSE]  hole[RESPONSE]  of[RESPONSE]  the[RESPONSE]  exact[RESPONSE]  same[RESPONSE]  mass[RESPONSE] ,[RESPONSE]  Earth[RESPONSE] ’[RESPONSE] s[RESPONSE]  orbit[RESPONSE]  wouldn[RESPONSE] ’[RESPONSE] t[RESPONSE]  change[RESPONSE] —[RESPONSE] it[RESPONSE]  would[RESPONSE]  just[RESPONSE]  get[RESPONSE]  very[RESPONSE]  dark[RESPONSE]  and[RESPONSE]  cold[RESPONSE] .

# [RESPONSE] So[RESPONSE]  in[RESPONSE]  short[RESPONSE] :[RESPONSE]  a[RESPONSE]  black[RESPONSE]  hole[RESPONSE]  is[RESPONSE]  an[RESPONSE]  object[RESPONSE]  so[RESPONSE]  dense[RESPONSE]  that[RESPONSE]  it[RESPONSE]  traps[RESPONSE]  light[RESPONSE]  itself[RESPONSE] ,[RESPONSE]  forming[RESPONSE]  when[RESPONSE]  a[RESPONSE]  massive[RESPONSE]  star[RESPONSE]  dies[RESPONSE]  and[RESPONSE]  collapses[RESPONSE] .
