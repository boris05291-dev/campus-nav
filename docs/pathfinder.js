// docs/pathfinder.js
// 負責：網頁版的「計算」部分，照 Python 版 core/graph.py、core/pathfinder.py、core/route.py 改寫。
// 這裡不碰畫面，所以也可以用 Node.js 直接執行，拿來和 Python 版比對結果。

// 讀進 JSON 資料，建立地點表和鄰接表（對應 Python 的 CampusGraph.load）
function buildGraph(data) {
  var graph = {
    places: {},      // 地點 id -> {name, type, x, y}
    adjacency: {},   // 地點 id -> [[相鄰地點 id, 距離], ...]
    edges: [],       // 所有道路
    edgeLookup: {}   // "a|b" -> 道路，兩個方向都記
  };

  // 第一步：登記所有地點，每個地點一開始沒有鄰居
  data.nodes.forEach(function (node) {
    graph.places[node.id] = { name: node.name, type: node.type, x: node.x, y: node.y };
    graph.adjacency[node.id] = [];
  });

  // 第二步：照 JSON 的順序加入雙向道路（順序要和 Python 一樣，結果才會一模一樣）
  data.edges.forEach(function (e) {
    var a = e.from, b = e.to, d = e.distance_m;
    if (!(a in graph.adjacency) || !(b in graph.adjacency)) {
      throw new Error("道路連到不存在的地點：" + a + " - " + b);
    }
    var path = e.path || [[graph.places[a].x, graph.places[a].y], [graph.places[b].x, graph.places[b].y]];
    graph.adjacency[a].push([b, d]);
    graph.adjacency[b].push([a, d]);
    var edge = { from: a, to: b, distance: d, path: path };
    graph.edges.push(edge);
    // 同兩點有好幾條路時只留最短的（和 Python 的 edge_lookup 一樣）
    [a + "|" + b, b + "|" + a].forEach(function (key) {
      if (!(key in graph.edgeLookup) || d < graph.edgeLookup[key].distance) {
        graph.edgeLookup[key] = edge;
      }
    });
  });
  return graph;
}

// 比較兩個 [距離, 地點id]：先比距離，一樣再比 id（和 Python 比較 tuple 的規則一樣）
function less(p, q) {
  return p[0] < q[0] || (p[0] === q[0] && p[1] < q[1]);
}

// 把一個項目放進 heap（最小堆積），對應 Python 的 heapq.heappush
function heapPush(heap, item) {
  heap.push(item);
  var i = heap.length - 1;
  // 比爸爸小就往上換
  while (i > 0) {
    var parent = Math.floor((i - 1) / 2);
    if (!less(heap[i], heap[parent])) break;
    var t = heap[i]; heap[i] = heap[parent]; heap[parent] = t;
    i = parent;
  }
}

// 拿出 heap 裡最小的項目，對應 Python 的 heapq.heappop
function heapPop(heap) {
  var top = heap[0];
  var last = heap.pop();
  if (heap.length > 0) {
    heap[0] = last;
    var i = 0;
    // 比小孩大就往下換
    while (true) {
      var left = 2 * i + 1, right = 2 * i + 2, smallest = i;
      if (left < heap.length && less(heap[left], heap[smallest])) smallest = left;
      if (right < heap.length && less(heap[right], heap[smallest])) smallest = right;
      if (smallest === i) break;
      var t = heap[i]; heap[i] = heap[smallest]; heap[smallest] = t;
      i = smallest;
    }
  }
  return top;
}

// 找出從 start 到 end 的最短路線，回傳 [路線, 總距離]（照 core/pathfinder.py 一行一行改寫）
// 走不到時回傳 [[], Infinity]
function dijkstra(graph, start, end) {
  if (!(start in graph.adjacency)) throw new Error("找不到起點：" + start);
  if (!(end in graph.adjacency)) throw new Error("找不到終點：" + end);

  var distances = {};   // 目前找到從起點到每個地點的最短距離
  distances[start] = 0;
  var previous = {};    // 最短路線上，每個地點是從哪裡走過來的
  var visited = {};     // 已經確定最短距離的地點
  var heap = [[0, start]];

  while (heap.length > 0) {
    var item = heapPop(heap);
    var currentDistance = item[0], current = item[1];

    // 同一個地點可能被放進 heap 好幾次，只處理第一次
    if (visited[current]) continue;
    visited[current] = true;

    // 終點已經確定，提早結束
    if (current === end) break;

    graph.adjacency[current].forEach(function (pair) {
      var neighbor = pair[0], distance = pair[1];
      if (visited[neighbor]) return;
      var newDistance = currentDistance + distance;
      if (!(neighbor in distances) || newDistance < distances[neighbor]) {
        distances[neighbor] = newDistance;
        previous[neighbor] = current;
        heapPush(heap, [newDistance, neighbor]);
      }
    });
  }

  if (!(end in distances)) return [[], Infinity];

  // 從終點沿著 previous 往回走到起點，再反轉
  var path = [end];
  while (path[path.length - 1] !== start) {
    path.push(previous[path[path.length - 1]]);
  }
  path.reverse();
  return [path, distances[end]];
}

// 回傳「從 a 走到 b」的道路折線點；反方向走就把折線倒過來（對應 edge_points）
function edgePoints(graph, a, b) {
  var edge = graph.edgeLookup[a + "|" + b];
  if (edge.from === a) return edge.path;
  return edge.path.slice().reverse();
}

// 去掉括號裡的長說明，例如「C 行政＆教學大樓（視覺特效…）」→「C 行政＆教學大樓」（對應 short_name）
function shortName(graph, id) {
  return graph.places[id].name.split("（")[0];
}

// 依照使用者打的文字推薦地點（路口不算），回傳排好順序的 id 清單（對應 graph.py 的 suggest）
// 排序：代號完全一樣 → 代號或名稱開頭一樣 → 名稱裡有打的每一個字 → 同一級再照名稱排
function suggest(graph, text) {
  text = text.trim().toLowerCase();
  var words = text.split(/\s+/).filter(function (w) { return w !== ""; });
  var results = [];
  for (var id in graph.places) {
    var place = graph.places[id];
    if (place.type === "junction") continue;
    var name = place.name.toLowerCase();
    var code = name.split(" ")[0];
    var score;
    if (text === "" || text === code) score = 0;
    else if (code.indexOf(text) === 0 || name.indexOf(text) === 0) score = 1;
    else if (words.every(function (w) { return name.indexOf(w) !== -1; })) score = 2;
    else continue;
    results.push([score, place.name, id]);
  }
  // 先比分數，一樣再比名稱、再比 id（和 Python 排 tuple 一樣）
  results.sort(function (a, b) {
    for (var i = 0; i < 3; i++) {
      if (a[i] < b[i]) return -1;
      if (a[i] > b[i]) return 1;
    }
    return 0;
  });
  return results.map(function (r) { return r[2]; });
}

// 用使用者打的文字找地點：名稱或代號完全一樣 → 推薦清單剛好只有一個；找不到或不只一個回傳 null（對應 find_place）
function findPlace(graph, text) {
  text = text.trim().toLowerCase();
  if (text === "") return null;
  for (var id in graph.places) {
    var place = graph.places[id];
    if (place.type === "junction") continue;
    var name = place.name.toLowerCase();
    if (text === name || text === name.split(" ")[0]) return id;
  }
  var ids = suggest(graph, text);
  return ids.length === 1 ? ids[0] : null;
}

// 「start → via → end」：跑兩次 dijkstra 再接起來，任何一段走不到就回傳 [[], Infinity]（對應 route_via）
function routeVia(graph, start, via, end) {
  var a = dijkstra(graph, start, via), b = dijkstra(graph, via, end);
  if (a[0].length === 0 || b[0].length === 0) return [[], Infinity];
  // b 的第一個點就是 via，已經在 a 的最後面了，所以跳過
  return [a[0].concat(b[0].slice(1)), a[1] + b[1]];
}

// 檢查使用者的選擇，沒問題才找路線，回傳 [路線, 總距離, 錯誤訊息]（對應 plan_route）
// start、end、via 是地點 id（找不到時是 null）；hasVia：途經點有沒有填字
function planRoute(graph, start, end, hasVia, via) {
  if (start === null) return [[], null, "找不到起點。請從推薦清單選一個地點。"];
  if (end === null) return [[], null, "找不到終點。請從推薦清單選一個地點。"];
  if (!hasVia) via = null;
  else if (via === null) return [[], null, "找不到途經點。請從推薦清單選一個地點，或把它清空。"];
  if (start === end && (via === null || via === start)) return [[], null, "起點和終點是同一個地方。"];

  var answer = via === null ? dijkstra(graph, start, end) : routeVia(graph, start, via, end);
  if (answer[0].length === 0) return [[], null, "這兩個地點之間沒有道路可以走到。"];
  return [answer[0], answer[1], null];
}

// 把路線整理成導航步驟：跳過路口，路口那幾段的距離加到下一站（對應 build_stops）
// 回傳 [[地點 id, 離上一站幾公尺, 離開上一站時怎麼轉], ...]；第一段不用轉，是 null
function buildStops(graph, path) {
  var stops = [[path[0], 0, null]];
  var walked = 0;
  var lastStopIndex = 0;   // 上一站在 path 裡的位置
  for (var i = 0; i < path.length - 1; i++) {
    walked = walked + graph.edgeLookup[path[i] + "|" + path[i + 1]].distance;
    var next = path[i + 1];
    if (graph.places[next].type !== "junction") {
      var turn = null;
      if (lastStopIndex > 0) {
        // 用「走進上一站的那條路」和「離開上一站的那條路」最靠近上一站的那一小段判斷轉彎
        var hereId = path[lastStopIndex];
        var roadIn = edgePoints(graph, path[lastStopIndex - 1], hereId);
        var roadOut = edgePoints(graph, hereId, path[lastStopIndex + 1]);
        var before = roadIn[roadIn.length - 2], after = roadOut[1];
        var here = graph.places[hereId];
        turn = turnText(before[0], before[1], here.x, here.y, after[0], after[1]);
      }
      stops.push([next, walked, turn]);
      walked = 0;
      lastStopIndex = i + 1;
    }
  }
  return stops;
}

// 依照兩個地點在地圖上的位置，回傳「箭頭 + 往哪個方向」，例如「↗ 往右上」（對應 direction_text）
// 畫面座標 y 往下變大，所以 dy 小於 0 是往上；一個方向比另一個大兩倍以上就只算那個方向
function directionText(x1, y1, x2, y2) {
  var dx = x2 - x1, dy = y2 - y1;
  if (Math.abs(dx) > 2 * Math.abs(dy)) return dx > 0 ? "→ 往右" : "← 往左";
  if (Math.abs(dy) > 2 * Math.abs(dx)) return dy < 0 ? "↑ 往上" : "↓ 往下";
  if (dx > 0 && dy < 0) return "↗ 往右上";
  if (dx < 0 && dy < 0) return "↖ 往左上";
  if (dx > 0) return "↘ 往右下";
  return "↙ 往左下";
}

// 從 (x1,y1) 走到 (x2,y2)，接著要去 (x3,y3)：在 (x2,y2) 要直走、左轉、右轉還是迴轉（對應 turn_text）
function turnText(x1, y1, x2, y2, x3, y3) {
  // 換算成角度的方式和 Python 的 math.degrees 一樣（除以 π/180），結果才會完全相同
  var angleIn = Math.atan2(y2 - y1, x2 - x1) / (Math.PI / 180);
  var angleOut = Math.atan2(y3 - y2, x3 - x2) / (Math.PI / 180);
  var turn = angleOut - angleIn;
  while (turn > 180) turn = turn - 360;
  while (turn <= -180) turn = turn + 360;
  if (Math.abs(turn) < 30) return "直走";
  if (Math.abs(turn) > 150) return "迴轉";
  return turn > 0 ? "右轉" : "左轉";
}

// 在 Node.js 裡執行時，把函式匯出給比對程式用；在瀏覽器裡沒有 module，會直接跳過
if (typeof module !== "undefined") {
  module.exports = {
    buildGraph: buildGraph, dijkstra: dijkstra, buildStops: buildStops, suggest: suggest,
    findPlace: findPlace, planRoute: planRoute, directionText: directionText
  };
}
