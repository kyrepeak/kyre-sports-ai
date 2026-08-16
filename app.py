from engine import *

st.title("🧠 KYRE SPORTS AI")
st.subheader("Sports Projection & Analytics Engine")
st.divider()

sport=st.selectbox("Choose Sport",["MLB","WNBA"])

if sport=="MLB":
    try:
        games_df,game_date=games_today()
    except requests.RequestException:
        games_df,game_date=pd.DataFrame(),datetime.now(ET).strftime("%Y-%m-%d")

    st.header("📡 Live MLB Data")
    if st.button("🔄 LOAD TODAY'S MLB GAMES",use_container_width=True):
        if games_df.empty:
            st.warning("No MLB games found.")
        else:
            st.success(f"Schedule loaded for {game_date}")
            show=games_df[["away_team","home_team","first_pitch_et","away_pitcher","home_pitcher","status"]].rename(columns={"away_team":"Away","home_team":"Home","first_pitch_et":"First Pitch (ET)","away_pitcher":"Away Pitcher","home_pitcher":"Home Pitcher","status":"Status"})
            st.dataframe(show,use_container_width=True,hide_index=True)

    st.divider()
    market=st.selectbox("Choose Market",["1+ Hit","2+ Hits","Home Run","Hits + Runs + RBIs","Moneyline","Run Line","Game Total"])

    if market=="1+ Hit":
        top_tab,single_tab=st.tabs(["🏆 Daily Top 5 Scanner","🔎 Single Player"])

        with top_tab:
            st.header("🏆 V12 Daily Top 5 — MLB 1+ Hit")
            st.write("Scans confirmed batting orders for actionable games, screens the full slate, then runs the V11 uncertainty engine on the strongest finalists.")
            include_live=st.checkbox("Include games already in progress",value=False)
            depth=st.selectbox("Slate Simulation Depth",["Fast — 100,000 per finalist","Standard — 500,000 per finalist","Deep — 1,000,000 per finalist"],index=1)
            sims={"Fast — 100,000 per finalist":100_000,"Standard — 500,000 per finalist":500_000,"Deep — 1,000,000 per finalist":1_000_000}[depth]

            if st.button("🔥 SCAN TODAY'S CONFIRMED LINEUPS",use_container_width=True):
                if games_df.empty:
                    st.error("Today's MLB schedule could not be loaded.")
                else:
                    with st.spinner("Reading today's confirmed lineups..."):
                        candidates,checked,with_lineups=slate_candidates(games_df,include_live)

                    if not candidates:
                        st.warning("No confirmed hitters were found in actionable games. Lineups may not be posted yet, or today's remaining games may already be underway/final.")
                    else:
                        st.info(f"Found {len(candidates)} confirmed hitters across {with_lineups}/{checked} actionable games.")
                        screened=[]
                        bar=st.progress(0,text="Screening confirmed hitters...")
                        for i,c in enumerate(candidates,1):
                            try:screened.append(prescreen(c))
                            except:pass
                            bar.progress(i/len(candidates),text=f"Screening hitters: {i}/{len(candidates)}")
                        bar.empty()

                        screened.sort(key=lambda x:x["screen_p1"],reverse=True)
                        finalists=screened[:min(8,len(screened))]
                        deep=[]
                        bar=st.progress(0,text="Running deep V12 models...")
                        for i,c in enumerate(finalists,1):
                            try:deep.append(deep_scan(c,sims))
                            except:pass
                            bar.progress(i/max(len(finalists),1),text=f"Deep modeling finalists: {i}/{len(finalists)}")
                        bar.empty()
                        deep.sort(key=lambda x:x["sim"]["p_one_plus"],reverse=True)
                        st.session_state["v12_results"]=deep

            if st.session_state.get("v12_results"):
                results=st.session_state["v12_results"]
                st.subheader("🥇 Today's Strongest 1+ Hit Projections")
                rows=[]
                for rank,r in enumerate(results[:5],1):
                    s=r["sim"]
                    rows.append({"Rank":rank,"Player":r["player_name"],"Team":r["team"],"Opponent":r["opponent"],"Starter":r["starter_name"],"Lineup":f"#{r['position']}","1+ Hit":f"{s['p_one_plus']*100:.1f}%","2+ Hits":f"{s['p_two_plus']*100:.1f}%","Expected Hits":f"{s['expected_hits']:.2f}","Fair 1+ Odds":odds(s["p_one_plus"]),"Confidence":r["confidence"],"Data":f"{r['data_score']}/8"})
                st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
                top=results[0]
                st.success(f"#1 right now: {top['player_name']} — {top['sim']['p_one_plus']*100:.1f}% projected 1+ hit probability, {top['confidence']} confidence.")
                st.caption("V12 ranks model probability, not sportsbook value. The scanner uses confirmed lineups only by default. It pre-screens the full slate, then deep-models up to eight finalists with starter/bullpen exposure, splits, recent form, park/weather, Statcast and Monte Carlo uncertainty. These are model estimates, not guarantees.")
                with st.expander("Show finalist details"):
                    detail=[]
                    for r in results:
                        s=r["sim"]
                        detail.append({"Player":r["player_name"],"Team":r["team"],"Opponent":r["opponent"],"Starter":r["starter_name"],"Spot":r["position"],"Season AVG":f"{r['season_avg']:.3f}","Screen 1+":f"{r['screen_p1']*100:.1f}%","Final 1+":f"{s['p_one_plus']*100:.1f}%","2+":f"{s['p_two_plus']*100:.1f}%","3+":f"{s['p_three_plus']*100:.1f}%","90% Scenario Range":f"{s['scenario_low']*100:.1f}%–{s['scenario_high']*100:.1f}%","MC SE":f"{s['mc_se']*100:.3f} pts","Confidence":r["confidence"]})
                    st.dataframe(pd.DataFrame(detail),use_container_width=True,hide_index=True)

        with single_tab:
            st.header("⚾ Single-Player Deep Analysis")
            name=st.text_input("Player Name",placeholder="Example: Yordan Alvarez")
            if st.button("📡 LOAD PLAYER + MATCHUP",use_container_width=True):
                st.session_state.pop("player_data",None)
                if not name.strip():
                    st.error("Enter a player name.")
                else:
                    try:
                        with st.spinner("Loading live hitter, matchup, Statcast and bullpen data..."):
                            d=load_player(name,games_df)
                        if d:st.session_state["player_data"]=d
                        else:st.error("Player not found.")
                    except requests.RequestException as exc:
                        st.error(f"Could not load MLB data: {exc}")

            if st.session_state.get("player_data"):
                d=st.session_state["player_data"]; p=d["player"]; stats=d["stats"]; recent=d.get("recent"); m=d.get("matchup"); pitch=d.get("pitcher"); sr=d.get("split_r"); sl=d.get("split_l"); e=d.get("environment"); sc=d.get("statcast"); bp=d.get("bullpen")
                if not stats:
                    st.error("No current-season hitting stats were found.")
                else:
                    st.success(f"Live data loaded for {p['name']}")
                    st.subheader(f"📊 {p['name']} — {stats['season']}")
                    st.caption(f"Team: {p['team_name']} • Bats: {p['bat_side']}")
                    metric_grid([("AVG",stats["avg"]),("Hits",stats["hits"]),("At-Bats",stats["at_bats"]),("Games",stats["games"]),("HR",stats["home_runs"]),("OBP",stats["obp"]),("SLG",stats["slg"]),("OPS",stats["ops"])])

                    st.subheader("🔥 Recent Form — Last 10 Games")
                    if recent and recent.get("avg") is not None:
                        metric_grid([("Recent AVG",f"{recent['avg']:.3f}"),("Hits",recent["hits"]),("Recent AB",recent["at_bats"]),("Hit Games",f"{recent['hit_games']}/{recent['games']}")])

                    st.subheader("📡 Statcast Contact Quality")
                    if sc:
                        metric_grid([("xBA",f"{sc['xba']:.3f}" if sc.get("xba") is not None else "N/A"),("Avg Exit Velo",f"{sc['avg_ev']:.1f} mph" if sc.get("avg_ev") is not None else "N/A"),("Hard-Hit %",f"{sc['hard_hit_rate']*100:.1f}%" if sc.get("hard_hit_rate") is not None else "N/A"),("Barrel %",f"{sc['barrel_rate']*100:.1f}%" if sc.get("barrel_rate") is not None else "N/A")])

                    st.subheader("⚔️ Today's Matchup")
                    if m:
                        metric_grid([("Opponent",m["opponent"]),("Home/Away",m["location"]),("First Pitch",m["first_pitch"]),("Status",m["status"])])
                        if pitch:
                            metric_grid([("Pitcher",pitch["name"]),("Throws",pitch["hand"]),("ERA",pitch["era"]),("WHIP",pitch["whip"]),("W-L",f"{pitch['wins']}-{pitch['losses']}"),("Starts",pitch["games_started"]),("IP",pitch["innings"]),("K/9",f"{pitch['k9']:.2f}" if pitch.get("k9") is not None else "N/A")])
                        sp=sr if pitch and pitch.get("hand")=="R" else sl if pitch and pitch.get("hand")=="L" else None
                        if sp:
                            st.subheader("↔️ Batter vs Starter Hand")
                            metric_grid([("Split AVG",sp["avg"]),("Split Hits",sp["hits"]),("Split AB",sp["at_bats"]),("Split OPS",sp["ops"])])

                        st.subheader("🧯 Opponent Bullpen")
                        if bp:
                            metric_grid([("Bullpen ERA",f"{bp['era']:.2f}"),("Bullpen WHIP",f"{bp['whip']:.2f}"),("Bullpen K/9",f"{bp['k9']:.2f}"),("Relievers",bp["reliever_count"]),("RHP Exposure",f"{bp['right_share']*100:.0f}%"),("LHP Exposure",f"{bp['left_share']*100:.0f}%")])

                        st.subheader("🏟️ Park + Weather")
                        ev=env_adj(e,m.get("venue_name","Unknown"))
                        metric_grid([("Ballpark",ev["venue_name"]),("Temperature",f"{ev['temperature']:.0f}°F" if ev["temperature"] is not None else "N/A"),("Condition",ev["condition"]),("Wind",ev["wind"]),("Roof Type",ev["roof_type"]),("Environment Grade",ev["grade"]),("Park Adj",f"{ev['park_adjustment']*100:+.1f}%")])
                    else:
                        st.warning("No game found today for this player's team.")

                    confirmed,estimated=d.get("confirmed_lineup"),d.get("recent_lineup")
                    projected=int(confirmed) if confirmed else int(estimated["position"]) if estimated else 4
                    source="Confirmed today's lineup" if confirmed else f"Recent lineup estimate ({estimated['sample_games']} games)" if estimated else "Manual fallback"
                    st.subheader("📋 Lineup Position")
                    metric_grid([("Projected Batting Spot",f"#{projected}"),("Lineup Source",source),("Baseline Expected AB",f"{ab_for_spot(projected):.1f}")],3)
                    spot=st.selectbox("Batting Order Used by Model",list(range(1,10)),index=projected-1)
                    expected_ab=st.number_input("Projected At-Bats Today",2.5,6.0,float(ab_for_spot(spot)),.1)
                    st.number_input("Sportsbook Hit Line",value=.5,step=.5)
                    mode=st.selectbox("Monte Carlo Simulation Size",["Quick — 500,000","Standard — 5,000,000","Deep — 10,000,000"],index=1)
                    sim_n={"Quick — 500,000":500_000,"Standard — 5,000,000":5_000_000,"Deep — 10,000,000":10_000_000}[mode]

                    if st.button("🔥 RUN V12 SINGLE-PLAYER MONTE CARLO",use_container_width=True):
                        base=sf(stats["avg"],0) or 0; z=model_inputs(base,spot,m,pitch,sr,sl,recent,e,sc,bp); ex=starter_exposure(pitch,expected_ab)
                        det=combined(z["starter_rate"],z["bullpen_rate"],ex["starter_ab"],ex["bullpen_ab"]); seed=sim_seed(p["id"],(m or {}).get("game_pk",0))
                        with st.spinner(f"Running {sim_n:,} Monte Carlo simulations..."):
                            sim=monte(z["starter_rate"],z["bullpen_rate"],expected_ab,ex["starter_share"],z["split_weight"],z["statcast_model"].get("reliability",0),z["pitcher_quality"].get("reliability",0) if z["pitcher_quality"] else 0,z["bullpen_quality"].get("reliability",0) if z["bullpen_quality"] else 0,sim_n,seed)
                        grade,score=confidence(stats,pitch,z["starter_split"],recent,confirmed,e,sc,bp,sim)
                        season_base=p_from_avg(base,expected_ab)
                        st.header("🧠 V12 Single-Player Model")
                        metric_grid([("Season AVG",f"{base:.3f}"),("Starter-Facing Rate",f"{z['starter_rate']:.3f}"),("Bullpen-Facing Rate",f"{z['bullpen_rate']:.3f}"),("Expected AB",f"{expected_ab:.1f}"),("Starter Exposure",f"{ex['starter_share']*100:.0f}%"),("V10 Deterministic 1+",f"{det['p_one_plus']*100:.1f}%"),("Environment Adj",f"{z['env_model']['total_adjustment']*100:+.1f}%"),("Contact Adj",f"{z['statcast_model']['quality_adjustment']*100:+.1f}%")])
                        st.subheader("🎲 Monte Carlo — Uncertainty Engine")
                        metric_grid([("Simulations",f"{sim['simulations']:,}"),("Batches",sim["batches"]),("Random Seed",sim["seed"]),("Convergence","PASS" if sim["converged"] else "CHECK"),("MC Standard Error",f"{sim['mc_se']*100:.3f} pts"),("Max Batch Spread",f"{sim['batch_range']*100:.2f} pts"),("Scenario 90% Range",f"{sim['scenario_low']*100:.1f}%–{sim['scenario_high']*100:.1f}%"),("Confidence Grade",grade)])
                        st.header("📊 V12 Simulation Results")
                        metric_grid([("Expected Hits",f"{sim['expected_hits']:.2f}"),("1+ Hit Probability",f"{sim['p_one_plus']*100:.1f}%"),("0 Hit Probability",f"{sim['p_zero']*100:.1f}%"),("Exactly 1 Hit",f"{sim['p_exact_one']*100:.1f}%"),("2+ Hit Probability",f"{sim['p_two_plus']*100:.1f}%"),("3+ Hit Probability",f"{sim['p_three_plus']*100:.1f}%"),("Median Hits",sim["median_hits"]),("Mode Hits",sim["mode_hits"]),("Fair Odds — 1+",odds(sim["p_one_plus"])),("Season AVG + Current AB",f"{season_base['p_one_plus']*100:.1f}%"),("Data Layers",f"{score}/8"),("Model Version","V12")])
                        st.caption("Season AVG + Current AB is the season batting-average baseline using today's projected at-bat count. It is not a context-free season probability.")

    else:
        st.info(f"The MLB {market} engine will be added later.")

else:
    market=st.selectbox("Choose Market",["Points","Rebounds","Assists","PRA","Spread","Game Total"])
    st.info(f"The WNBA {market} model will be added later.")

st.divider()
st.caption("Kyre Sports AI • Projection Engine V12")
