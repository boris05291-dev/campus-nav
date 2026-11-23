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

// 把路線整理成站點：跳過路口，路口那幾段的距離加到下一站（對應 build_stops，但不算轉彎）
// 回傳 [[地點 id, 離上一站幾公尺], ...]
function buildStops(graph, path) {
  var stops = [[path[0], 0]];
  var walked = 0;
  for (var i = 0; i < path.length - 1; i++) {
    walked = walked + graph.edgeLookup[path[i] + "|" + path[i + 1]].distance;
    var next = path[i + 1];
    if (graph.places[next].type !== "junction") {
      stops.push([next, walked]);
      walked = 0;
    }
  }
  return stops;
}

// 在 Node.js 裡執行時，把函式匯出給比對程式用；在瀏覽器裡沒有 module，會直接跳過
if (typeof module !== "undefined") {
  module.exports = { buildGraph: buildGraph, dijkstra: dijkstra, buildStops: buildStops };
}
