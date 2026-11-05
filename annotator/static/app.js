/* Pairwise annotator — client logic (no framework, no build step). */
(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const state = {
    annotator: localStorage.getItem("annotator") || "",
    item: null,
    scores: { left: {}, right: {} },
    preference: null,
    startedAt: null,
  };

  // ---- helpers -----------------------------------------------------------------
  const api = async (url, opts) => {
    const res = await fetch(url, opts);
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
    return body;
  };

  const setError = (msg) => { $("#error").textContent = msg || ""; };

  const canonical = (side) => {
    // Map the on-screen side back to the stored A/B, undoing the random swap.
    if (side === "tie") return "tie";
    const swapped = state.item.swapped;
    if (side === "left") return swapped ? "B" : "A";
    return swapped ? "A" : "B";
  };

  // ---- rendering ---------------------------------------------------------------
  const resetForm = () => {
    state.scores = { left: {}, right: {} };
    state.preference = null;
    $$(".pip").forEach((b) => b.classList.remove("on"));
    $$(".choice").forEach((b) => b.classList.remove("on"));
    $$(".response").forEach((r) => r.classList.remove("preferred"));
    $("#rationale").value = "";
    setError("");
  };

  const renderItem = (payload) => {
    const { item, done, total } = payload;
    $("#progress").hidden = false;
    $("#progress-text").textContent = `${done} / ${total}`;
    $("#progress-fill").style.width = total ? `${(100 * done) / total}%` : "0%";
    if (!item) {
      $("#main").hidden = true;
      $("#done").hidden = false;
      return;
    }
    state.item = item;
    state.startedAt = performance.now();
    $("#main").hidden = false;
    $("#done").hidden = true;
    $("#prompt").textContent = item.prompt;
    $("#left").textContent = item.left;
    $("#right").textContent = item.right;
    resetForm();
    window.scrollTo({ top: 0 });
  };

  const loadNext = async () => {
    const payload = await api(`/api/next?annotator=${encodeURIComponent(state.annotator)}`);
    renderItem(payload);
  };

  // ---- interactions ----------------------------------------------------------------
  const choose = (side) => {
    state.preference = side;
    $$(".choice").forEach((b) => b.classList.toggle("on", b.dataset.pref === side));
    $$(".response").forEach((r) => r.classList.toggle("preferred", r.dataset.side === side));
  };

  const submit = async () => {
    if (!state.item) return;
    if (!state.preference) return setError("Pick which response is better (1, 2 or 3).");
    const rationale = $("#rationale").value.trim();
    if (rationale.length < 10) return setError("Write a rationale of at least 10 characters.");

    const scores = { A: canonicalScores("A"), B: canonicalScores("B") };
    const payload = {
      annotator: state.annotator,
      item_id: state.item.id,
      preference: canonical(state.preference),
      scores,
      rationale,
      swapped: state.item.swapped,
      seconds_spent: (performance.now() - state.startedAt) / 1000,
    };
    try {
      $("#submit").disabled = true;
      await api("/api/annotations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      await loadNext();
    } catch (err) {
      setError(err.message);
    } finally {
      $("#submit").disabled = false;
    }
  };

  const canonicalScores = (ab) => {
    const side = canonical("left") === ab ? "left" : "right";
    return state.scores[side];
  };

  const start = async () => {
    const name = $("#annotator").value.trim();
    if (!name) return setError("Enter your name first.");
    state.annotator = name;
    localStorage.setItem("annotator", name);
    await loadNext();
  };

  // ---- wiring -------------------------------------------------------------------------
  $("#annotator").value = state.annotator;
  $("#start").addEventListener("click", start);
  $("#annotator").addEventListener("keydown", (e) => { if (e.key === "Enter") start(); });

  $$(".scale").forEach((scale) => {
    scale.addEventListener("click", (e) => {
      const pip = e.target.closest(".pip");
      if (!pip) return;
      const { side, criterion } = scale.dataset;
      state.scores[side][criterion] = Number(pip.dataset.value);
      scale.querySelectorAll(".pip").forEach((b) => b.classList.toggle("on", b === pip));
    });
  });

  $$(".choice").forEach((b) => b.addEventListener("click", () => choose(b.dataset.pref)));
  $("#submit").addEventListener("click", submit);

  document.addEventListener("keydown", (e) => {
    const typing = e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT";
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) return submit();
    if (typing) return;
    if (e.key === "1") choose("left");
    if (e.key === "2") choose("right");
    if (e.key === "3") choose("tie");
  });

  if (state.annotator) loadNext().catch((err) => setError(err.message));
})();
