// docs/app.js
// 負責：網頁版的畫面。讀 map_data.json → 畫地圖（SVG）→ 下拉選單、點地圖選地點 → 按下「開始導航」畫出路線。
// 計算的部分（建圖、Dijkstra、整理站點）在 pathfinder.js。

var SVG_NS = "http://www.w3.org/2000/svg";
var WALK_SPEED = 70;   // 每分鐘走 70 公尺，和 Python 版 config.py 一樣
var PLACE_COLORS = { building: "#2F6FB0", facility: "#3A9D5D", gate: "#D9822B" };

// 風景的座標，從 ui/scenery.py 複製過來（只是裝飾，和找路線無關）
var LAND = [[380, 250], [420, 180], [500, 130], [600, 95], [700, 60], [780, 55], [860, 70], [960, 80], [1060, 120], [1150, 150], [1260, 160], [1360, 175], [1480, 180], [1600, 185], [1600, 640], [1450, 630], [1300, 640], [1150, 650], [1050, 690], [950, 740], [860, 770], [720, 775], [690, 700], [680, 600], [640, 520], [560, 470], [470, 460], [400, 430], [370, 340]];
var LAKES = [
  [[430, 400], [470, 383], [520, 392], [575, 385], [610, 402], [585, 428], [530, 432], [485, 450], [440, 432]],
  [[1195, 375], [1220, 352], [1265, 350], [1305, 362], [1300, 395], [1260, 410], [1215, 402]]
];
var FIELDS = [[850, 600, 920, 650, "#D9C3BE"], [690, 600, 738, 700, "#D9C3BE"], [1010, 194, 1062, 232, "#D9C3BE"], [955, 298, 985, 328, "#D9C3BE"], [940, 418, 966, 442, "#B5574A"], [972, 418, 998, 442, "#B5574A"], [903, 226, 931, 240, "#4E8FB5"]];
var BUILDINGS = [["J", 0, 0, 50, 30, "#8FD3CF"], ["A", 0, 0, 30, 24, "#F2C9A8"], ["B", 0, 0, 60, 40, "#EBA58F"], ["P7", 0, 0, 30, 24, "#D9B3E0"], ["K", 0, 0, 40, 30, "#F4E7C5"], ["I", 0, 0, 70, 26, "#E6EFD0"], ["H", 0, 0, 60, 30, "#9C8CC7"], ["D", 0, 0, 44, 28, "#8FD3CF"], ["C", 0, 0, 60, 22, "#EBA58F"], ["F", 0, 0, 40, 24, "#EBA58F"], ["P6", 0, 0, 50, 30, "#8FB8DE"], ["M", 0, 17, 50, 30, "#F4EED8"], ["Nd", 7, 15, 50, 30, "#F4EED8"], ["L", 0, 0, 30, 24, "#B9D9A0"]];

var graph = null;
var svg = document.getElementById("map");
var startInput = document.getElementById("start");
var viaInput = document.getElementById("via");
var endInput = document.getElementById("end");
var resultBox = document.getElementById("result");
var routeLayer = null;   // 放路線的圖層，要清掉路線時只清這一層

// 建立一個 SVG 元素，attrs 是屬性，例如 {cx: 10, fill: "red"}
function el(tag, attrs, parent) {
  var node = document.createElementNS(SVG_NS, tag);
  for (var key in attrs) node.setAttribute(key, attrs[key]);
  parent.appendChild(node);
  return node;
}

// 把 [[x, y], ...] 變成 "x,y x,y ..."，給 polyline 用
function pointsText(points) {
  return points.map(function (p) { return p[0] + "," + p[1]; }).join(" ");
}

// 把外框點變成圓滑的封閉曲線（和 tkinter 的 smooth=True 一樣：曲線經過相鄰兩點的中點）
function smoothPath(points) {
  var n = points.length;
  function mid(i) {
    var a = points[i % n], b = points[(i + 1) % n];
    return ((a[0] + b[0]) / 2) + "," + ((a[1] + b[1]) / 2);
  }
  var d = "M" + mid(0);
  for (var i = 1; i <= n; i++) d += " Q" + points[i % n][0] + "," + points[i % n][1] + " " + mid(i);
  return d + "Z";
}

// 畫綠地、湖、操場、場地、建築物
function drawScenery() {
  el("path", { d: smoothPath(LAND), fill: "#A9C48A" }, svg);
  LAKES.forEach(function (lake) {
    el("path", { d: smoothPath(lake), fill: "#5DB8A8", stroke: "#3E9886", "stroke-width": 2 }, svg);
  });
  el("ellipse", { cx: 1010, cy: 517.5, rx: 60, ry: 37.5, fill: "#C8624F", stroke: "#A84F3F" }, svg);
  el("ellipse", { cx: 1010, cy: 517.5, rx: 51, ry: 28.5, fill: "#8FBF6A", stroke: "#F0F0F0" }, svg);
  el("ellipse", { cx: 682.5, cy: 319, rx: 22.5, ry: 21, fill: "#E3D3C3", stroke: "#C9B5A3" }, svg);
  FIELDS.forEach(function (f) {
    el("rect", { x: f[0], y: f[1], width: f[2] - f[0], height: f[3] - f[1], fill: f[4], stroke: "#B8A39C" }, svg);
  });
  BUILDINGS.forEach(function (b) {
    var p = graph.places[b[0]];
    var x = p.x + b[1] - b[3] / 2, y = p.y + b[2] - b[4] / 2;
    el("rect", { x: x + 3, y: y + 3, width: b[3], height: b[4], fill: "#7E9A66" }, svg);   // 影子
    el("rect", { x: x, y: y, width: b[3], height: b[4], fill: b[5], stroke: "#7A7A7A" }, svg);
  });
}

// 畫道路：先畫全部的綠色邊線，再畫白色路面，路口才會接得乾淨
function drawRoads() {
  [["#8CA872", 8], ["#FFFFFF", 5]].forEach(function (style) {
    graph.edges.forEach(function (e) {
      el("polyline", { points: pointsText(e.path), fill: "none", stroke: style[0], "stroke-width": style[1], "stroke-linecap": "round", "stroke-linejoin": "round" }, svg);
    });
  });
}

// 檢查兩個方框 {x, y, width, height} 有沒有重疊
function overlap(a, b) {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

// 畫可以選的地點（圓點 + 名稱），點下去就選成起點或終點
// 名稱依序試「下、右、左、上」，都不行再試「更下面、更上面」，用第一個不會蓋到別的名稱或圓點的位置
function drawPlaces() {
  var ids = Object.keys(graph.places).filter(function (id) { return graph.places[id].type !== "junction"; });
  var taken = [];   // 已經被圓點或名稱佔用的範圍
  var groups = {};

  // 第一輪：畫圓點
  ids.forEach(function (id) {
    var p = graph.places[id];
    var g = el("g", { "class": "place", tabindex: 0, role: "button", "aria-label": p.name }, svg);
    el("title", {}, g).textContent = p.name;   // 滑鼠移上去會顯示全名
    el("circle", { cx: p.x, cy: p.y, r: 16, fill: "transparent" }, g);   // 看不見的大圓，手機比較好點
    el("circle", { cx: p.x, cy: p.y, r: 6, fill: PLACE_COLORS[p.type] || PLACE_COLORS.facility, stroke: "#fff", "stroke-width": 2 }, g);
    g.addEventListener("click", function () { pickFromMap(id); });
    g.addEventListener("keydown", function (event) { if (event.key === "Enter") pickFromMap(id); });
    taken.push({ x: p.x - 6, y: p.y - 6, width: 12, height: 12 });
    groups[id] = g;
  });

  // 第二輪：放名稱
  ids.forEach(function (id) {
    var p = graph.places[id];
    var text = el("text", {}, groups[id]);
    text.textContent = shortName(graph, id).split("、")[0];
    var positions = [[0, 9, "middle", "hanging"], [9, 0, "start", "middle"], [-9, 0, "end", "middle"], [0, -9, "middle", "auto"], [0, 28, "middle", "hanging"], [0, -28, "middle", "auto"]];
    for (var i = 0; i <= positions.length; i++) {
      var pos = positions[i % positions.length];   // 四個都重疊就回到「下面」
      text.setAttribute("x", p.x + pos[0]);
      text.setAttribute("y", p.y + pos[1]);
      text.setAttribute("text-anchor", pos[2]);
      text.setAttribute("dominant-baseline", pos[3]);
      var box = text.getBBox();
      if (i === positions.length || !taken.some(function (t) { return overlap(box, t); })) {
        taken.push(box);
        break;
      }
    }
  });
}

// 讓一個輸入框有「推薦清單」（對應 Python 版的 SearchBox）
// 點進去或打字就用 suggest 推薦地點；↑↓ 移動、Enter 選定、Esc 收起；選好後執行 onEnter
function setupSearchBox(input, onEnter) {
  var list = document.getElementById(input.id + "-list");
  var suggestions = [];
  var selected = 0;

  // 依照輸入框的字重新產生推薦清單，預設選第一筆（最像的）
  function update() {
    suggestions = suggest(graph, input.value);
    selected = 0;
    list.innerHTML = "";
    suggestions.forEach(function (id, index) {
      var li = document.createElement("li");
      li.id = input.id + "-opt-" + index;
      li.setAttribute("role", "option");
      li.textContent = graph.places[id].name;
      // 用 mousedown 而不是 click：click 發生前輸入框就失去焦點、清單已經收起來了
      li.addEventListener("mousedown", function (event) {
        event.preventDefault();
        selected = index;
        choose();
      });
      list.appendChild(li);
    });
    if (suggestions.length === 0) hide();
    else { list.hidden = false; input.setAttribute("aria-expanded", "true"); highlight(); }
  }

  // 標出目前選到的那一筆，並捲到看得見的地方
  function highlight() {
    for (var i = 0; i < list.children.length; i++) {
      list.children[i].setAttribute("aria-selected", i === selected ? "true" : "false");
    }
    input.setAttribute("aria-activedescendant", input.id + "-opt-" + selected);
    list.children[selected].scrollIntoView({ block: "nearest" });
  }

  // 收起推薦清單
  function hide() {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  }

  // 把選到的地點填進輸入框，收起清單，然後做下一步
  function choose() {
    if (!list.hidden && suggestions.length > 0) input.value = graph.places[suggestions[selected]].name;
    hide();
    onEnter();
  }

  input.addEventListener("focus", update);
  input.addEventListener("input", update);
  input.addEventListener("blur", hide);
  input.addEventListener("keydown", function (event) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (list.hidden) return update();
      var step = event.key === "ArrowDown" ? 1 : -1;
      selected = Math.max(0, Math.min(selected + step, suggestions.length - 1));
      highlight();
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose();
    } else if (event.key === "Escape") {
      hide();
    }
  });
}

// 點地圖上的地點（和 Python 版 fill_from_map 一樣）
// 起點還空著、或起終點都已經填好（要重新開始）→ 填進起點並清掉終點；只有起點填好 → 填進終點並直接找路線
function pickFromMap(id) {
  var name = graph.places[id].name;
  if (startInput.value.trim() === "" || endInput.value.trim() !== "") {
    startInput.value = name;
    endInput.value = "";
    clearRoute();
    showMarker(id, "#2E7D32");
    resultBox.innerHTML = '<p class="note">已選起點，請再點一個地點當終點。</p>';
  } else {
    endInput.value = name;
    findRoute();
  }
}

// 清掉地圖上的路線和起終點標記
function clearRoute() {
  routeLayer.innerHTML = "";
}

// 在地點上畫一個有白邊的大圓點，標示起點（綠）或終點（紅）
function showMarker(id, color) {
  var p = graph.places[id];
  el("circle", { cx: p.x, cy: p.y, r: 9, fill: color, stroke: "#fff", "stroke-width": 3 }, routeLayer);
}

// 顯示一行錯誤訊息
function showError(message) {
  clearRoute();
  resultBox.innerHTML = '<p class="error">' + message + "</p>";
}

// 按下「開始導航」：檢查選擇並找路線（plan_route）→ 畫紅線 → 列出每一站、轉彎、方向、總距離、步行時間
function findRoute() {
  var answer = planRoute(
    graph,
    findPlace(graph, startInput.value),
    findPlace(graph, endInput.value),
    viaInput.value.trim() !== "",
    findPlace(graph, viaInput.value)
  );
  var path = answer[0], total = answer[1];
  if (answer[2] !== null) return showError(answer[2]);
  var start = path[0], end = path[path.length - 1];

  // 把每一段道路的折線接起來；下一段的第一個點和上一段最後一個點一樣，所以跳過
  var points = [];
  for (var i = 0; i < path.length - 1; i++) {
    var segment = edgePoints(graph, path[i], path[i + 1]);
    points = points.concat(i > 0 ? segment.slice(1) : segment);
  }
  clearRoute();
  var line = el("polyline", { "class": "route-line", points: pointsText(points), fill: "none", stroke: "#D7262B", "stroke-width": 6, "stroke-linecap": "round", "stroke-linejoin": "round" }, routeLayer);
  // 路線從起點「畫」到終點：先把虛線間隔設成整條線的長度，再讓 CSS 動畫把它收回來
  var length = line.getTotalLength();
  line.style.strokeDasharray = length;
  line.style.strokeDashoffset = length;
  showMarker(start, "#2E7D32");
  showMarker(end, "#C62828");

  // 步行時間：和 Python 版一樣，總距離 ÷ 70，取到小數第 1 位
  var html = '<div class="summary"><div><b>' + total + '</b><span>公尺</span></div>' +
             '<div><b>' + (total / WALK_SPEED).toFixed(1) + '</b><span>分鐘步行</span></div></div><ol class="trail">';
  var stops = buildStops(graph, path);
  stops.forEach(function (stop, index) {
    // 每一站前面先寫「怎麼轉、往哪個方向、走幾公尺」，第一站是起點所以不用（和 Python 版 show_result 一樣）
    if (index > 0) {
      var a = graph.places[stops[index - 1][0]], b = graph.places[stop[0]];
      var arrow = directionText(a.x, a.y, b.x, b.y);
      var turn = stop[2] === null ? "" : "<b>" + stop[2] + "</b>，";
      html += '<li class="leg">' + turn + arrow + " 走 " + stop[1] + " 公尺</li>";
    }
    html += '<li class="stop">' + shortName(graph, stop[0]) + "</li>";
  });
  resultBox.innerHTML = html + "</ol>";
}

// 程式開始：讀資料 → 畫地圖 → 綁定按鈕
fetch("map_data.json")
  .then(function (response) { return response.json(); })
  .then(function (data) {
    graph = buildGraph(data);
    drawScenery();
    drawRoads();
    routeLayer = el("g", {}, svg);   // 路線在道路上面、地點下面
    drawPlaces();
    // 起點選好跳到終點；途經點選好也跳到終點；終點選好直接找路線（和 Python 版一樣）
    setupSearchBox(startInput, function () { endInput.focus(); });
    setupSearchBox(viaInput, function () { endInput.focus(); });
    setupSearchBox(endInput, findRoute);
    document.getElementById("go").addEventListener("click", findRoute);
    // 交換起點和終點的文字；兩個都是有效地點就直接找回程（途經點不動）
    document.getElementById("swap").addEventListener("click", function () {
      var t = startInput.value;
      startInput.value = endInput.value;
      endInput.value = t;
      if (findPlace(graph, startInput.value) !== null && findPlace(graph, endInput.value) !== null) findRoute();
    });
  })
  .catch(function (error) {
    resultBox.innerHTML = '<p class="error">讀不到地圖資料：' + error + "</p>";
  });
