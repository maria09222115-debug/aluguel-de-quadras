const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const brl = v => Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

function aviso(msg) {
  const el = $("#aviso");
  el.textContent = msg;
  el.classList.add("mostra");
  clearTimeout(aviso.t);
  aviso.t = setTimeout(() => el.classList.remove("mostra"), 2800);
}

async function api(url, method = "GET", body) {
  const r = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.erro || "Algo deu errado.");
  return d;
}

const tentar = fn => async (...a) => { try { await fn(...a); } catch (e) { aviso(e.message); } };

/* ---------- abas ---------- */
function abrirAba(id) {
  $$(".aba").forEach(b => b.classList.toggle("ativa", b.dataset.aba === id));
  $$(".painel").forEach(p => p.classList.toggle("ativo", p.id === id));
}
$$(".aba").forEach(b => b.addEventListener("click", () => abrirAba(b.dataset.aba)));

/* ---------- sessão ---------- */
function definirSessao(u) {
  document.body.classList.toggle("logado", !!u);
  $("#quem").textContent = u ? `${u.nome} (${u.perfil})` : "Visitante";
  $("#btn-sair").hidden = !u;
  if (u) $$("table[data-res]").forEach(t => carregar(t.dataset.res));
}

$("#f-login").addEventListener("submit", tentar(async e => {
  e.preventDefault();
  const u = await api("/api/login", "POST", Object.fromEntries(new FormData(e.target)));
  e.target.reset(); definirSessao(u); aviso("Login feito."); abrirAba("quadras");
}));

$("#f-cadastro").addEventListener("submit", tentar(async e => {
  e.preventDefault();
  await api("/api/register", "POST", Object.fromEntries(new FormData(e.target)));
  e.target.reset(); aviso("Conta criada. Agora entre com seu e-mail.");
}));

$("#btn-sair").addEventListener("click", tentar(async () => {
  await api("/api/logout", "POST"); definirSessao(null); abrirAba("acesso");
}));

/* ---------- CRUD genérico ---------- */
const dados = {};

function celula(f, v) {
  if (f === "preco_hora") return brl(v);
  if (f === "status") {
    const bom = ["Disponível", "Resolvido"].includes(v);
    return `<span class="selo ${bom ? "ok" : "alerta"}">${v}</span>`;
  }
  return String(v ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function carregar(res) {
  const t = $(`table[data-res="${res}"]`);
  const cols = $$("th[data-f]", t).map(th => th.dataset.f);
  const lista = dados[res] = await api(`/api/${res}`);
  const corpo = $("tbody", t);
  if (!lista.length) {
    corpo.innerHTML = `<tr><td class="vazio" colspan="${cols.length + 1}">Nada cadastrado ainda. Use o formulário ao lado.</td></tr>`;
    return;
  }
  corpo.innerHTML = lista.map(r => {
    const baixo = res === "stock" && r.quantidade <= r.minimo ? ' class="baixo" title="Estoque baixo"' : "";
    return `<tr${baixo}>${cols.map(c => `<td>${celula(c, r[c])}</td>`).join("")}
      <td class="botoes"><button class="sec" data-ed="${r.id}">Editar</button><button data-del="${r.id}">Excluir</button></td></tr>`;
  }).join("");
}

$$("form.crud").forEach(form => {
  const res = form.dataset.res;
  const limpar = () => { form.reset(); form.elements.id.value = ""; };

  form.addEventListener("submit", tentar(async e => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(form));
    const id = d.id; delete d.id;
    if (id) await api(`/api/${res}/${id}`, "PUT", d);
    else await api(`/api/${res}`, "POST", d);
    limpar(); await carregar(res); aviso("Salvo.");
  }));

  $(".cancelar", form).addEventListener("click", limpar);

  $(`table[data-res="${res}"]`).addEventListener("click", tentar(async e => {
    const ed = e.target.dataset.ed, del = e.target.dataset.del;
    if (ed) {
      const r = dados[res].find(x => x.id == ed);
      Object.entries(r).forEach(([k, v]) => { if (form.elements[k]) form.elements[k].value = v; });
      form.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
    if (del && confirm("Excluir este registro?")) {
      await api(`/api/${res}/${del}`, "DELETE");
      await carregar(res); aviso("Excluído.");
    }
  }));
});

api("/api/me").then(u => definirSessao(u.logado ? u : null));
