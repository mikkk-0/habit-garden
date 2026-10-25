"use strict";

const $ = (selector) => document.querySelector(selector);
const state = { tasks: [], today: "", archived: false, editing: null, month: null, days: new Set(), selectedEmoji: "🌱", emojiCatalog: null, emojiCategory: "favorites", emojiLimit: 96 };
const monthNames = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"];
const weekdayNames = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"];
const emojiCategories = [
  ["favorites", "Частые"], ["Smileys & Emotion", "Смайлы"], ["People & Body", "Люди"],
  ["Animals & Nature", "Природа"], ["Food & Drink", "Еда"], ["Travel & Places", "Места"],
  ["Activities", "Занятия"], ["Objects", "Предметы"], ["Symbols", "Символы"], ["Flags", "Флаги"],
];
const favoriteEmoji = ["🌱", "📚", "💧", "🏃", "🧘", "💪", "🍎", "🥗", "☕", "🪥", "💊", "🛌", "😴", "🚶", "🚴", "🏋️", "✍️", "📝", "💻", "🎨", "🎸", "🎵", "🧹", "🧺", "💰", "📅", "⏰", "❤️", "☀️", "🌙", "🌿", "🌸", "🐾", "🏠", "🧠", "🎯", "🔥", "⭐", "✅", "🫶"];
let toastTimer;
let midnightTimer;
let emojiCatalogPromise;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Не удалось выполнить действие");
  return result;
}

function localDate(iso) { return new Date(`${iso}T12:00:00`); }
function isoDate(year, month, day) { return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`; }
function formatDate(iso) { return localDate(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" }); }
function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 3200);
}
function report(error) { showToast(error.message || String(error)); }

async function loadEmojiCatalog() {
  if (!emojiCatalogPromise) {
    emojiCatalogPromise = api("/emoji-catalog.json").then((catalog) => {
      state.emojiCatalog = catalog;
      state.emojiBySymbol = new Map(catalog.items.map((item) => [item[0], item]));
      setSelectedEmoji(state.selectedEmoji);
      return catalog;
    }).catch((error) => { emojiCatalogPromise = null; throw error; });
  }
  return emojiCatalogPromise;
}

function setSelectedEmoji(emoji) {
  state.selectedEmoji = emoji;
  $("#selectedEmoji").textContent = emoji;
  const item = state.emojiBySymbol?.get(emoji);
  $("#emojiName").textContent = item ? item[1] : "Метка задания";
}

function closeEmojiPicker() {
  $("#emojiPicker").hidden = true;
  $("#emojiTrigger").setAttribute("aria-expanded", "false");
}

function renderEmojiCategories() {
  const container = $("#emojiCategories");
  container.replaceChildren();
  for (const [key, label] of emojiCategories) {
    const button = document.createElement("button");
    button.type = "button"; button.className = "emoji-category"; button.textContent = label;
    button.classList.toggle("active", key === state.emojiCategory);
    button.addEventListener("click", () => { state.emojiCategory = key; state.emojiLimit = 96; $("#emojiSearch").value = ""; renderEmojiCategories(); renderEmojiGrid(); });
    container.append(button);
  }
}

function matchingEmoji() {
  const query = $("#emojiSearch").value.trim().toLocaleLowerCase("ru-RU");
  if (query) return state.emojiCatalog.items.filter(([emoji, name, keywords]) => `${emoji} ${name} ${keywords}`.toLocaleLowerCase("ru-RU").includes(query));
  if (state.emojiCategory === "favorites") return favoriteEmoji.map((emoji) => state.emojiBySymbol.get(emoji)).filter(Boolean);
  return state.emojiCatalog.items.filter((item) => item[3] === state.emojiCategory);
}

function renderEmojiGrid() {
  const items = matchingEmoji();
  const grid = $("#emojiGrid");
  const fragment = document.createDocumentFragment();
  for (const [emoji, name] of items.slice(0, state.emojiLimit)) {
    const button = document.createElement("button");
    button.type = "button"; button.className = "emoji-choice"; button.textContent = emoji;
    button.title = name; button.setAttribute("aria-label", name);
    button.classList.toggle("selected", emoji === state.selectedEmoji);
    button.addEventListener("click", () => { setSelectedEmoji(emoji); closeEmojiPicker(); $("#emojiTrigger").focus(); });
    fragment.append(button);
  }
  grid.replaceChildren(fragment);
  $("#emojiCount").textContent = `${items.length} эмодзи`;
  $("#emojiEmpty").hidden = items.length !== 0;
  $("#emojiMore").hidden = items.length <= state.emojiLimit;
}

async function toggleEmojiPicker() {
  if (!$("#emojiPicker").hidden) { closeEmojiPicker(); return; }
  await loadEmojiCatalog();
  $("#emojiPicker").hidden = false;
  $("#emojiTrigger").setAttribute("aria-expanded", "true");
  renderEmojiCategories(); renderEmojiGrid();
  $("#emojiSearch").focus();
}

async function refresh() {
  const data = await api("/api/tasks");
  state.tasks = data.tasks;
  state.today = data.today;
  render();
  clearTimeout(midnightTimer);
  const nextMidnight = new Date();
  nextMidnight.setHours(24, 0, 1, 0);
  midnightTimer = setTimeout(() => refresh().catch(report), nextMidnight - new Date());
}

function render() {
  const active = state.tasks.filter((task) => !task.archived);
  const archived = state.tasks.filter((task) => task.archived);
  const done = active.filter((task) => task.completed_today).length;
  $("#todayLabel").textContent = localDate(state.today).toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" });
  $("#todayCount").textContent = `${done} / ${active.length}`;
  $("#todayBar").style.width = `${active.length ? (done / active.length) * 100 : 0}%`;
  $("#activeAmount").textContent = active.length;
  $("#archiveAmount").textContent = archived.length;
  $("#activeTab").classList.toggle("active", !state.archived);
  $("#archiveTab").classList.toggle("active", state.archived);
  const tasks = state.archived ? archived : active;
  const grid = $("#taskGrid");
  grid.replaceChildren(...tasks.map(createCard));
  $("#emptyState").hidden = tasks.length !== 0;
  $("#emptyState h2").textContent = state.archived ? "Архив пока пуст" : "Здесь скоро появятся привычки";
  $("#emptyState p").textContent = state.archived ? "Сюда можно перенести задания, которые больше не нужны каждый день." : "Начните с одного небольшого дела, которое хочется делать каждый день.";
  $("#emptyAdd").hidden = state.archived;
}

function createCard(task) {
  const card = document.createElement("article");
  card.className = `task-card${task.completed_today ? " is-done" : ""}${task.archived ? " is-archived" : ""}`;
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.setAttribute("aria-label", `${task.name}. ${task.completed_today ? "Выполнено сегодня" : "Не выполнено сегодня"}. Открыть настройки: Shift+Enter`);
  const top = document.createElement("div"); top.className = "card-top";
  const icons = document.createElement("div"); icons.className = "card-icons";
  const emoji = document.createElement("span"); emoji.className = "card-emoji"; emoji.textContent = task.label_emoji;
  const symbol = document.createElement("span"); symbol.className = "status-symbol"; symbol.textContent = task.completed_today ? task.symbol_on : task.symbol_off;
  icons.append(emoji, symbol);
  const menu = document.createElement("button"); menu.className = "more-button"; menu.type = "button"; menu.textContent = "···"; menu.setAttribute("aria-label", `Календарь и настройки: ${task.name}`);
  menu.addEventListener("click", (event) => { event.stopPropagation(); openEdit(task.id); });
  top.append(icons, menu);
  const name = document.createElement("h3"); name.textContent = task.name;
  const stats = document.createElement("div"); stats.className = "card-stats";
  for (const [value, label] of [[task.streak, "стрик, дней"], [task.total_days, "всего дней"], [`${task.completion_percent}%`, "выполнено"]]) {
    if (stats.childNodes.length) { const divider = document.createElement("i"); divider.className = "stat-divider"; stats.append(divider); }
    const item = document.createElement("div"); item.className = "stat";
    const strong = document.createElement("strong"); strong.textContent = value;
    const small = document.createElement("small"); small.textContent = label;
    item.append(strong, small); stats.append(item);
  }
  const progress = document.createElement("div"); progress.className = "progress";
  const fill = document.createElement("span"); fill.style.width = `${task.completion_percent}%`; progress.append(fill);
  const bottom = document.createElement("div"); bottom.className = "card-bottom";
  const created = document.createElement("span"); created.textContent = `с ${formatDate(task.created_on)}`;
  const today = document.createElement("span"); today.className = task.completed_today ? "done-indicator" : ""; today.textContent = task.completed_today ? "✓ сегодня" : "○ сегодня";
  bottom.append(created, today);
  card.append(top, name, stats, progress, bottom);
  card.addEventListener("click", () => { if (task.archived) openEdit(task.id); else setToday(task, true); });
  card.addEventListener("auxclick", (event) => { if (event.button === 1) { event.preventDefault(); if (!task.archived) setToday(task, false); } });
  card.addEventListener("mousedown", (event) => { if (event.button === 1) event.preventDefault(); });
  card.addEventListener("contextmenu", (event) => { event.preventDefault(); openEdit(task.id); });
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); if (event.shiftKey || task.archived) openEdit(task.id); else setToday(task, true); }
    if (event.key === "Delete" && !task.archived) { event.preventDefault(); setToday(task, false); }
  });
  return card;
}

async function setToday(task, completed) {
  if (task.completed_today === completed) return;
  try {
    await api(`/api/tasks/${task.id}/days/${state.today}`, { method: "PUT", body: JSON.stringify({ completed }) });
    await refresh();
    if (state.editing === task.id) await loadMonth();
  } catch (error) { report(error); }
}

function openNew() {
  state.editing = null;
  $("#taskForm").reset();
  closeEmojiPicker();
  state.emojiCategory = "favorites";
  state.emojiLimit = 96;
  setSelectedEmoji("🌱");
  $("#dialogEyebrow").textContent = "НОВОЕ ЗАДАНИЕ";
  $("#dialogTitle").textContent = "Что будем делать?";
  $("#calendarArea").hidden = true;
  $("#archiveButton").hidden = true;
  $("#clearToday").hidden = true;
  $("#taskDialog").showModal();
  $("#taskName").focus();
}

async function openEdit(id) {
  const task = state.tasks.find((item) => item.id === id);
  if (!task) return;
  state.editing = id;
  state.month = { year: Number(state.today.slice(0, 4)), month: Number(state.today.slice(5, 7)) - 1 };
  $("#taskName").value = task.name;
  closeEmojiPicker();
  state.emojiCategory = "favorites";
  state.emojiLimit = 96;
  setSelectedEmoji(task.label_emoji);
  $("#symbolOff").value = task.symbol_off;
  $("#symbolOn").value = task.symbol_on;
  $("#reminderTime").value = task.reminder_time;
  $("#dialogEyebrow").textContent = "КАЛЕНДАРЬ И НАСТРОЙКИ";
  $("#dialogTitle").textContent = task.name;
  $("#calendarArea").hidden = false;
  $("#archiveButton").hidden = false;
  $("#archiveButton").textContent = task.archived ? "Восстановить" : "В архив";
  $("#clearToday").hidden = task.archived || !task.completed_today;
  $("#taskDialog").showModal();
  try { await loadMonth(); } catch (error) { report(error); }
}

async function loadMonth() {
  const task = state.tasks.find((item) => item.id === state.editing);
  if (!task) return;
  const { year, month } = state.month;
  const data = await api(`/api/tasks/${task.id}/month?year=${year}&month=${month + 1}`);
  state.days = new Set(data.days);
  renderCalendar(task);
}

function renderCalendar(task) {
  const { year, month } = state.month;
  $("#monthLabel").textContent = `${monthNames[month]} ${year}`;
  const calendar = $("#calendar"); calendar.replaceChildren();
  for (const name of weekdayNames) { const label = document.createElement("div"); label.className = "weekday"; label.textContent = name; calendar.append(label); }
  const offset = (new Date(year, month, 1).getDay() + 6) % 7;
  for (let i = 0; i < offset; i++) calendar.append(document.createElement("div"));
  const last = new Date(year, month + 1, 0).getDate();
  for (let day = 1; day <= last; day++) {
    const iso = isoDate(year, month, day);
    const button = document.createElement("button"); button.type = "button"; button.className = "day"; button.textContent = day;
    const before = iso < task.created_on, future = iso > state.today;
    button.disabled = before || future || task.archived;
    button.classList.toggle("before", before);
    button.classList.toggle("future", future);
    button.classList.toggle("today", iso === state.today);
    button.classList.toggle("done", state.days.has(iso));
    if (!button.disabled) button.addEventListener("click", async () => {
      try {
        await api(`/api/tasks/${task.id}/days/${iso}`, { method: "PUT", body: JSON.stringify({ completed: !state.days.has(iso) }) });
        await refresh(); await loadMonth();
        const updated = state.tasks.find((item) => item.id === task.id);
        $("#clearToday").hidden = !updated.completed_today;
      } catch (error) { report(error); }
    });
    calendar.append(button);
  }
}

$("#newButton").addEventListener("click", openNew);
$("#emptyAdd").addEventListener("click", openNew);
$("#closeDialog").addEventListener("click", () => $("#taskDialog").close());
$("#emojiTrigger").addEventListener("click", () => toggleEmojiPicker().catch(report));
$("#emojiSearch").addEventListener("input", () => { state.emojiLimit = 96; renderEmojiGrid(); });
$("#emojiSearch").addEventListener("keydown", (event) => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); closeEmojiPicker(); $("#emojiTrigger").focus(); } });
$("#emojiMore").addEventListener("click", () => { state.emojiLimit += 96; renderEmojiGrid(); });
$("#taskDialog").addEventListener("close", closeEmojiPicker);
$("#activeTab").addEventListener("click", () => { state.archived = false; render(); });
$("#archiveTab").addEventListener("click", () => { state.archived = true; render(); });
$("#prevMonth").addEventListener("click", () => { state.month.month--; if (state.month.month < 0) { state.month.month = 11; state.month.year--; } loadMonth().catch(report); });
$("#nextMonth").addEventListener("click", () => { state.month.month++; if (state.month.month > 11) { state.month.month = 0; state.month.year++; } loadMonth().catch(report); });
$("#clearToday").addEventListener("click", async () => {
  const task = state.tasks.find((item) => item.id === state.editing);
  if (task) await setToday(task, false);
  $("#clearToday").hidden = true;
});
$("#archiveButton").addEventListener("click", async () => {
  const task = state.tasks.find((item) => item.id === state.editing);
  if (!task) return;
  try {
    await api(`/api/tasks/${task.id}`, { method: "PATCH", body: JSON.stringify({ archived: !task.archived }) });
    $("#taskDialog").close(); await refresh();
    showToast(task.archived ? "Задание восстановлено" : "Задание в архиве");
  } catch (error) { report(error); }
});
$("#taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = { name: $("#taskName").value, label_emoji: state.selectedEmoji, reminder_time: $("#reminderTime").value, symbol_off: $("#symbolOff").value, symbol_on: $("#symbolOn").value };
  try {
    if (state.editing) await api(`/api/tasks/${state.editing}`, { method: "PATCH", body: JSON.stringify(payload) });
    else await api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
    $("#taskDialog").close(); await refresh();
    showToast(state.editing ? "Изменения сохранены" : "Задание создано");
  } catch (error) { report(error); }
});

refresh().catch(report);
loadEmojiCatalog().catch(report);
document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh().catch(report); });
