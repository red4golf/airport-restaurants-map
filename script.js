const map = L.map("map", { zoomControl: true }).setView([39.5, -98.35], 4);

// OSM tiles (no key)
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

let allFeatures = [];
let markerLayer = L.layerGroup().addTo(map);

const typeFilter = document.getElementById("typeFilter");
const regionFilter = document.getElementById("regionFilter");
const searchInput = document.getElementById("searchInput");
const resetBtn = document.getElementById("resetBtn");
const listEl = document.getElementById("list");
const resultCountEl = document.getElementById("resultCount");

function normalize(s) {
  return (s || "").toString().toLowerCase().trim();
}

function buildPopup(props) {
  const lines = [];
  lines.push(`<div style="font-weight:700;font-size:14px;">${props.restaurant_name || props.name || "Unnamed"}</div>`);
  const ident = props.airport_ident || props.icao || "";
  const aname = props.airport_name || "";
  const loc = [props.city, props.state].filter(Boolean).join(", ");
  lines.push(`<div style="margin-top:4px;color:#6b7280;font-size:12px;">
    ${ident ? `<b>${ident}</b> — ` : ""}${aname}${loc ? ` • ${loc}` : ""}
  </div>`);

  if (props.hours) lines.push(`<div style="margin-top:8px;font-size:12px;"><b>Hours:</b> ${props.hours}</div>`);
  if (props.walk_time_min != null) lines.push(`<div style="font-size:12px;"><b>Walk:</b> ${props.walk_time_min} min</div>`);
  if (props.notes) lines.push(`<div style="margin-top:8px;font-size:12px;">${props.notes}</div>`);

  const links = [];
  if (props.website) links.push(`<a href="${props.website}" target="_blank" rel="noopener">Website</a>`);
  if (props.substack_post) links.push(`<a href="${props.substack_post}" target="_blank" rel="noopener">Read review</a>`);
  if (links.length) lines.push(`<div style="margin-top:10px;font-size:12px;display:flex;gap:10px;">${links.join("")}</div>`);

  return lines.join("");
}

function clearMarkers() {
  markerLayer.clearLayers();
  listEl.innerHTML = "";
}

function addCard(feature, marker) {
  const p = feature.properties || {};
  const name = p.restaurant_name || p.name || "Unnamed";
  const ident = p.airport_ident || p.icao || "";
  const aname = p.airport_name || "";
  const loc = [p.city, p.state].filter(Boolean).join(", ");

  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `
    <div class="name">${name}</div>
    <div class="meta">
      ${ident ? `${ident} — ` : ""}${aname}${loc ? ` • ${loc}` : ""}
    </div>
    <div class="tags">
      <span class="tag">${p.type || "unknown"}</span>
      ${p.region ? `<span class="tag">${p.region}</span>` : ""}
      ${p.iso_region ? `<span class="tag">${p.iso_region}</span>` : ""}
      ${p.walk_time_min != null ? `<span class="tag">${p.walk_time_min} min walk</span>` : ""}
    </div>
  `;
  card.addEventListener("click", () => {
    const latlng = marker.getLatLng();
    map.setView(latlng, Math.max(map.getZoom(), 13), { animate: true });
    marker.openPopup();
  });
  listEl.appendChild(card);
}

function populateRegionFilter(features) {
  const regions = new Set();
  features.forEach(f => {
    const r = f.properties?.region;
    if (r) regions.add(r);
  });
  regionFilter.innerHTML = `<option value="all">All</option>`;
  [...regions].sort().forEach(r => {
    const opt = document.createElement("option");
    opt.value = r;
    opt.textContent = r;
    regionFilter.appendChild(opt);
  });
}

function applyFilters() {
  const typeVal = typeFilter.value;
  const regionVal = regionFilter.value;
  const q = normalize(searchInput.value);

  const filtered = allFeatures.filter(f => {
    const p = f.properties || {};
    const okType = (typeVal === "all") || (p.type === typeVal);
    const okRegion = (regionVal === "all") || (p.region === regionVal);

    const hay = normalize([
      p.restaurant_name, p.name, p.airport_ident, p.icao, p.airport_name, p.city, p.state, p.notes
    ].filter(Boolean).join(" "));

    const okSearch = !q || hay.includes(q);
    return okType && okRegion && okSearch;
  });

  clearMarkers();

  const bounds = [];
  filtered.forEach(f => {
    const [lng, lat] = f.geometry.coordinates;
    const p = f.properties || {};
    const marker = L.marker([lat, lng]).addTo(markerLayer);
    marker.bindPopup(buildPopup(p));
    addCard(f, marker);
    bounds.push([lat, lng]);
  });

  resultCountEl.textContent = `${filtered.length} location${filtered.length === 1 ? "" : "s"}`;
  if (bounds.length) map.fitBounds(bounds, { padding: [30, 30] });
}

async function init() {
  const res = await fetch("./data/restaurants.geojson", { cache: "no-store" });
  const geojson = await res.json();
  allFeatures = geojson.features || [];

  populateRegionFilter(allFeatures);
  applyFilters();

  typeFilter.addEventListener("change", applyFilters);
  regionFilter.addEventListener("change", applyFilters);
  searchInput.addEventListener("input", () => {
    window.clearTimeout(window.__t);
    window.__t = window.setTimeout(applyFilters, 120);
  });
  resetBtn.addEventListener("click", () => {
    typeFilter.value = "all";
    regionFilter.value = "all";
    searchInput.value = "";
    applyFilters();
  });
}

init();
