-- Abilita RLS su tutte le tabelle pubbliche
ALTER TABLE public.spy_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.players ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.games ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.player_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.secret_hitler_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.spy_locations ENABLE ROW LEVEL SECURITY;

-- Crea policy permissive (ALLOW ALL) per evitare blocchi dell'applicazione
-- Nota: In produzione dovresti restringere queste policy!

CREATE POLICY "allow_all_spy_roles" ON public.spy_roles FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_players" ON public.players FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_rooms" ON public.rooms FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_games" ON public.games FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_player_roles" ON public.player_roles FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_secret_hitler_states" ON public.secret_hitler_states FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_spy_locations" ON public.spy_locations FOR ALL USING (true) WITH CHECK (true);
