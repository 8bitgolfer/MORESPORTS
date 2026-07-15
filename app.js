let DATA = [];
let GAMES = [];
let selectedGames = new Set();
let current = null;
let activeTab = "last10";

let sortKey = "edge";
let sortDirection = "desc";

const fmt = value => {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "—";
  }

  return Number.isInteger(number)
    ? String(number)
    : number.toFixed(1);
};

const avg = games => {
  if (!games.length) {
    return 0;
  }

  return games.reduce(
    (sum, game) => sum + Number(game.value || 0),
    0
  ) / games.length;
};

const rate = (games, line) => {
  if (!games.length) {
    return 0;
  }

  const overs = games.filter(
    game => Number(game.value) > Number(line)
  ).length;

  return Math.round((overs / games.length) * 100);
};

const gameKey = game =>
  game.id ||
  `${game.away_team}-${game.home_team}-${game.date}`;

const propGameKey = prop =>
  prop.game_id ||
  `${prop.home ? prop.opponent : prop.team}-${
    prop.home ? prop.team : prop.opponent
  }-${prop.game_date || ""}`;

function localTime(iso) {
  if (!iso) {
    return "";
  }

  const date = new Date(iso);

  return (
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      hour: "numeric",
      minute: "2-digit"
    }).format(date) + " ET"
  );
}

function getSortValue(prop, key) {
  const last10 = prop.last10 || [];
  const last5 = last10.slice(0, 5);
  const h2h = prop.h2h || [];

  switch (key) {
    case "player":
      return prop.player?.toLowerCase() || "";

    case "line":
      return Number(prop.line) || 0;

    case "l5Avg":
      return avg(last5);

    case "l10Avg":
      return avg(last10);

    case "h2hAvg":
      return h2h.length ? avg(h2h) : -Infinity;

    case "projection":
      return Number(prop.projection) || 0;

    case "edge":
      return (
        (Number(prop.projection) || 0) -
        (Number(prop.line) || 0)
      );

    case "l10Over":
      return rate(last10, prop.line);

    default:
      return 0;
  }
}

function sortProps(props) {
  return [...props].sort((a, b) => {
    const aValue = getSortValue(a, sortKey);
    const bValue = getSortValue(b, sortKey);

    let comparison = 0;

    if (
      typeof aValue === "string" &&
      typeof bValue === "string"
    ) {
      comparison = aValue.localeCompare(bValue);
    } else {
      comparison = Number(aValue) - Number(bValue);
    }

    return sortDirection === "asc"
      ? comparison
      : -comparison;
  });
}

async function init() {
  const response = await fetch(
    `data/props.json?${Date.now()}`
  );

  const json = await response.json();

  DATA = (json.props || []).filter(
    prop => prop.market === "pts"
  );

  GAMES = json.games || deriveGames(DATA);
  selectedGames = new Set(GAMES.map(gameKey));

  document.querySelector("#updatedAt").textContent =
    "Last updated: " +
    (json.updated_at || "manual data");

  renderGames();
  populateTeams();
  setupSorting();
  render();
}

function deriveGames(props) {
  const map = new Map();

  props.forEach(prop => {
    const away = prop.home
      ? prop.opponent
      : prop.team;

    const home = prop.home
      ? prop.team
      : prop.opponent;

    const id =
      prop.game_id ||
      `${away}-${home}-${prop.game_date || ""}`;

    if (!map.has(id)) {
      map.set(id, {
        id,
        date: prop.game_date || "",
        datetime: prop.game_datetime || "",
        away_team: away,
        home_team: home
      });
    }
  });

  return [...map.values()];
}

function renderGames() {
  const container = document.querySelector("#games");

  if (!GAMES.length) {
    container.innerHTML =
      '<span class="noGames">No WNBA games found for this slate.</span>';
    return;
  }

  container.innerHTML = GAMES.map(game => {
    const key = gameKey(game);
    const active = selectedGames.has(key);

    return `
      <button
        class="gameChip ${active ? "active" : ""}"
        data-game="${key}"
      >
        <span>
          <b>${game.away_team}</b>
          @
          <b>${game.home_team}</b>
        </span>

        <small>
          ${localTime(game.datetime) || game.time || ""}
        </small>
      </button>
    `;
  }).join("");

  container
    .querySelectorAll(".gameChip")
    .forEach(button => {
      button.onclick = () => {
        const key = button.dataset.game;

        if (selectedGames.has(key)) {
          selectedGames.delete(key);
        } else {
          selectedGames.add(key);
        }

        renderGames();
        render();
      };
    });

  document.querySelector("#selectAllGames").textContent =
    selectedGames.size === GAMES.length
      ? "Clear all"
      : "Select all";
}

function populateTeams() {
  const teams = [
    ...new Set(
      DATA.map(prop => prop.team).filter(Boolean)
    )
  ].sort();

  document.querySelector("#team").innerHTML =
    '<option value="all">All teams</option>' +
    teams
      .map(team => `<option>${team}</option>`)
      .join("");
}

function filteredData() {
  const query = document
    .querySelector("#search")
    .value
    .toLowerCase();

  const team = document.querySelector("#team").value;

  return DATA.filter(prop => {
    const selectedGame =
      selectedGames.has(propGameKey(prop));

    const matchesPlayer =
      prop.player.toLowerCase().includes(query);

    const matchesTeam =
      team === "all" || prop.team === team;

    return (
      selectedGame &&
      matchesPlayer &&
      matchesTeam
    );
  });
}

function setupSorting() {
  document
    .querySelectorAll("th.sortable")
    .forEach(header => {
      header.addEventListener("click", () => {
        const newSortKey = header.dataset.sort;

        if (sortKey === newSortKey) {
          sortDirection =
            sortDirection === "desc"
              ? "asc"
              : "desc";
        } else {
          sortKey = newSortKey;
          sortDirection =
            newSortKey === "player"
              ? "asc"
              : "desc";
        }

        updateSortHeaders();
        render();
      });
    });

  updateSortHeaders();
}

function updateSortHeaders() {
  document
    .querySelectorAll("th.sortable")
    .forEach(header => {
      header.classList.remove(
        "sort-active",
        "sort-asc",
        "sort-desc"
      );

      if (header.dataset.sort === sortKey) {
        header.classList.add(
          "sort-active",
          sortDirection === "asc"
            ? "sort-asc"
            : "sort-desc"
        );
      }
    });
}

function render() {
  const filtered = filteredData();
  const sorted = sortProps(filtered);

  document.querySelector("#rows").innerHTML =
    sorted.map(prop => {
      const last10 = prop.last10 || [];
      const last5 = last10.slice(0, 5);
      const h2h = prop.h2h || [];

      const projection =
        Number(prop.projection) || 0;

      const edge =
        projection - Number(prop.line);

      return `
        <tr data-id="${DATA.indexOf(prop)}">
          <td>
            <span class="player">
              ${prop.player}
            </span>

            <span class="sub">
              ${prop.team || ""}
              ${prop.position ? ` · ${prop.position}` : ""}
            </span>
          </td>

          <td>
            ${
              prop.team
                ? `${prop.team} ${
                    prop.home ? "vs" : "@"
                  } ${prop.opponent}`
                : prop.matchup || "—"
            }
          </td>

          <td>
            <span class="pill">
              ${prop.market_label}
            </span>

            <span class="book">
              ${
                prop.bookmaker_label ||
                prop.bookmaker ||
                ""
              }
            </span>
          </td>

          <td>${fmt(prop.line)}</td>

          <td>
            ${last5.length ? fmt(avg(last5)) : "—"}
          </td>

          <td>
            ${last10.length ? fmt(avg(last10)) : "—"}
          </td>

          <td>
            ${h2h.length ? fmt(avg(h2h)) : "—"}
          </td>

          <td>
            ${
              Number.isFinite(
                Number(prop.projection)
              )
                ? fmt(prop.projection)
                : "—"
            }
          </td>

          <td class="${
            edge >= 0 ? "positive" : "negative"
          }">
            ${
              Number.isFinite(edge)
                ? `${edge >= 0 ? "+" : ""}${fmt(edge)}`
                : "—"
            }
          </td>

          <td class="rate">
            ${
              last10.length
                ? `${rate(last10, prop.line)}%`
                : "—"
            }
          </td>
        </tr>
      `;
    }).join("") ||
    `
      <tr>
        <td colspan="10" class="empty">
          No props match the selected game(s).
        </td>
      </tr>
    `;

  document.querySelector("#propCount").textContent =
    filtered.length;

  const best = [...filtered].sort(
    (a, b) =>
      rate(b.last10 || [], b.line) -
      rate(a.last10 || [], a.line)
  )[0];

  document.querySelector("#bestRate").textContent =
    best && (best.last10 || []).length
      ? `${best.player} ${rate(
          best.last10 || [],
          best.line
        )}%`
      : "—";

  const propsWithProjection = filtered.filter(
    prop =>
      Number.isFinite(Number(prop.projection))
  );

  document.querySelector("#avgEdge").textContent =
    propsWithProjection.length
      ? fmt(
          propsWithProjection.reduce(
            (sum, prop) =>
              sum +
              (Number(prop.projection) -
                Number(prop.line)),
            0
          ) / propsWithProjection.length
        )
      : "—";

  document
    .querySelectorAll("tbody tr[data-id]")
    .forEach(row => {
      row.onclick = () =>
        openModal(DATA[Number(row.dataset.id)]);
    });
}

function openModal(prop) {
  current = prop;
  activeTab = "last10";

  document.querySelector("#modalName").textContent =
    prop.player;

  document.querySelector(
    "#modalMatchup"
  ).textContent =
    prop.team
      ? `${prop.team} ${
          prop.home ? "vs" : "@"
        } ${prop.opponent}${
          prop.game_datetime
            ? ` · ${localTime(
                prop.game_datetime
              )}`
            : ""
        }`
      : prop.matchup || "";

  document.querySelector(
    "#modalMarket"
  ).textContent =
    `${prop.market_label} · ${
      prop.bookmaker_label ||
      prop.bookmaker ||
      "Sportsbook"
    }`.toUpperCase();

  document.querySelector("#modalLine").textContent =
    fmt(prop.line);

  document.querySelector(
    "#modalProjection"
  ).textContent =
    Number.isFinite(Number(prop.projection))
      ? fmt(prop.projection)
      : "—";

  const edge =
    Number(prop.projection) -
    Number(prop.line);

  document.querySelector("#modalEdge").textContent =
    Number.isFinite(edge)
      ? `${edge >= 0 ? "+" : ""}${fmt(edge)}`
      : "—";

  document.querySelector("#modalEdge").className =
    edge >= 0 ? "positive" : "negative";

  document.querySelector("#modalH2H").textContent =
    (prop.h2h || []).length
      ? `${rate(prop.h2h || [], prop.line)}%`
      : "—";

  document
    .querySelectorAll(".tabs button")
    .forEach(button => {
      button.classList.toggle(
        "active",
        button.dataset.tab === "last10"
      );
    });

  draw();
  document.querySelector("#modalBack").hidden = false;
}

function draw() {
  const games =
    activeTab === "last5"
      ? (current.last10 || []).slice(0, 5)
      : activeTab === "h2h"
        ? current.h2h || []
        : current.last10 || [];

  document.querySelector("#periodLabel").textContent =
    activeTab === "h2h"
      ? "H2H Over %"
      : activeTab === "last5"
        ? "L5 Over %"
        : "L10 Over %";

  document.querySelector("#modalOver").textContent =
    games.length
      ? `${rate(games, current.line)}%`
      : "—";

  const max = Math.max(
    Number(current.line) * 1.35,
    ...games.map(game => Number(game.value)),
    1
  );

  document.querySelector("#chart").innerHTML =
    games.length
      ? games.map(game => {
          const value = Number(game.value);
          const line = Number(current.line);

          const resultClass =
            value > line
              ? "green"
              : value < line
                ? "red"
                : "push";

          return `
            <div class="gameRow">
              <span>
                ${game.date}
                ${
                  game.opponent
                    ? ` vs ${game.opponent}`
                    : ""
                }
              </span>

              <div class="track">
                <div
                  class="bar ${resultClass}"
                  style="width:${Math.max(
                    4,
                    (value / max) * 100
                  )}%"
                ></div>
              </div>

              <span class="gameVal">
                ${fmt(game.value)}
              </span>
            </div>
          `;
        }).join("")
      : "<p>No games available.</p>";
}

document
  .querySelectorAll("#search,#market,#team")
  .forEach(element => {
    element.addEventListener("input", render);
  });

document.querySelector("#selectAllGames").onclick =
  () => {
    selectedGames =
      selectedGames.size === GAMES.length
        ? new Set()
        : new Set(GAMES.map(gameKey));

    renderGames();
    render();
  };

document.querySelector("#closeModal").onclick =
  () => {
    document.querySelector("#modalBack").hidden =
      true;
  };

document.querySelector("#modalBack").onclick =
  event => {
    if (event.target.id === "modalBack") {
      event.currentTarget.hidden = true;
    }
  };

document
  .querySelectorAll(".tabs button")
  .forEach(button => {
    button.onclick = () => {
      activeTab = button.dataset.tab;

      document
        .querySelectorAll(".tabs button")
        .forEach(tab => {
          tab.classList.toggle(
            "active",
            tab === button
          );
        });

      draw();
    };
  });

init();
