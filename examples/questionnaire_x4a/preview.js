/* Private preview over a deliberately small, source-safe experimental overlay. */
(() => {
  const data = window.X4A_DATA;
  const results = document.getElementById("results");
  const card = document.getElementById("card");
  if (!data || !Array.isArray(data.charities)) { card.textContent = "Preview data is unavailable."; return; }
  function element(tag, text, cls) { const node = document.createElement(tag); if (text != null) node.textContent = text; if (cls) node.className = cls; return node; }
  function pill(text, cls) { return element("span", text, "pill " + cls); }
  function answerRow(a) {
    const row = element("div", null, "answer");
    row.append(element("p", a.question));
    const value = element("p"); value.append(pill(a.kind, a.tone), element("strong", a.value)); row.append(value);
    if (a.note) row.append(element("p", a.note, "meta"));
    row.append(element("p", a.period + " · " + a.source, "meta"));
    return row;
  }
  function render(c) {
    card.replaceChildren();
    const header = element("div", null, "card-header"); const title = element("div");
    title.append(element("div", "PRIVATE EXPERIMENTAL PREVIEW", "eyebrow"), element("h1", c.name), element("p", "ABN " + c.abn, "muted")); header.append(title); card.append(header);
    card.append(element("p", "These are source-reported and model-assessed experimental results. Program identities are provisional; nothing shown is a canonical or current-service claim.", "intro"));
    if (c.finance) {
      const section = element("section"); section.append(element("h2", "Fundraising expenditure"), pill("Source reported", "source"));
      section.append(element("p", new Intl.NumberFormat("en-AU", {style:"currency", currency:c.finance.currency, maximumFractionDigits:0}).format(c.finance.amount), "number"));
      section.append(element("p", c.finance.scope), element("p", c.finance.period + " · " + c.finance.source, "muted")); card.append(section);
    }
    const section = element("section"); section.append(element("h2", "Programs"), element("p", "Program details retain their source period and may not describe current operations.", "muted"));
    for (const p of c.programs) {
      const block = element("div", null, "program"); block.append(element("h3", p.name), pill("ACNC source reported", "source"));
      block.append(element("p", p.country + " · " + p.period, "muted"));
      if (!p.answers.length) block.append(element("p", "No questionnaire answers are available.", "muted"));
      for (const a of p.answers) block.append(answerRow(a)); section.append(block);
    }
    card.append(section);
    const sources = element("section"); sources.append(element("h2", "Sources")); const list = element("ul", null, "source-list");
    for (const s of c.sources) { const item = element("li"); const link = element("a", s.label); link.href = s.url; link.target = "_blank"; link.rel = "noopener noreferrer"; item.append(link); list.append(item); }
    sources.append(list, element("p", "Links identify the source material; model selections are not source quotations or independently verified facts.", "muted")); card.append(sources);
  }
  function choose(index) { [...results.children].forEach((b, i) => { b.classList.toggle("selected", i === index); b.setAttribute("aria-pressed", String(i === index)); }); render(data.charities[index]); }
  data.charities.forEach((c, i) => { const button = element("button", null, "result"); button.type = "button"; button.append(element("strong", c.name), element("small", "ABN " + c.abn)); button.addEventListener("click", () => choose(i)); results.append(button); });
  choose(0);
})();
