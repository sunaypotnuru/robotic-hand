import json

data = json.load(open('luna_call_graph.json'))
g = data['graph']
nodes = g['nodes']
edges = g['edges']

vis_nodes = []
vis_edges = []

node_iter = nodes.items() if isinstance(nodes, dict) else enumerate(nodes)
for uid, node in node_iter:
    name = node.get('name', '')
    label = node.get('label', '')
    label_clean = label.split(':', 1)[-1].strip()[:35]
    color = '#00f3ff'
    if 'app' in name:        color = '#00f3ff'
    if 'gesture' in name:    color = '#ff6b6b'
    if 'hand_detect' in name: color = '#ffa500'
    if 'hand_track' in name: color = '#ffcc44'
    if 'voice' in name:      color = '#00ff88'
    if 'kinematic' in name:  color = '#ff00ff'
    if 'motion' in name:     color = '#ffff00'
    if 'object' in name:     color = '#ff4444'
    if 'validator' in name:  color = '#44aaff'
    vis_nodes.append({'id': node['uid'], 'label': label_clean, 'title': name, 'color': {'background': color, 'border': '#111', 'highlight': {'background': '#fff'}}})

edge_iter = edges.items() if isinstance(edges, dict) else enumerate(edges)
for uid, edge in edge_iter:
    vis_edges.append({'from': edge['source'], 'to': edge['target'], 'arrows': 'to', 'color': {'color': 'rgba(0,243,255,0.4)'}})

graph_json = json.dumps({'nodes': vis_nodes, 'edges': vis_edges}, indent=2)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>LUNA - Codebase Call Graph</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.css"/>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #050505; color: #fff; font-family: 'Courier New', monospace; overflow: hidden; }}
  #header {{ padding: 12px 24px; background: rgba(0,243,255,0.05); border-bottom: 1px solid rgba(0,243,255,0.2); display:flex; justify-content:space-between; align-items:center; }}
  #header h1 {{ color: #00f3ff; font-size: 1.2rem; letter-spacing: 4px; }}
  #header p {{ color: #888; font-size: 0.8rem; }}
  #legend {{ display:flex; gap:15px; font-size:0.72rem; }}
  .dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; margin-right:5px; }}
  #mynetwork {{ width: 100vw; height: calc(100vh - 56px); background: #080808; }}
  #tooltip {{ position:fixed; top:10px; right:10px; background:rgba(0,0,0,0.85); border:1px solid #00f3ff; padding:10px 15px; border-radius:6px; font-size:0.8rem; color:#aaa; max-width:280px; display:none; }}
  #stats {{ position:fixed; bottom:10px; left:10px; background:rgba(0,0,0,0.7); border:1px solid rgba(0,243,255,0.2); padding:8px 14px; border-radius:4px; font-size:0.75rem; color:#555; }}
</style>
</head>
<body>
<div id="header">
  <div>
    <h1>&#129302; LUNA — CODEBASE CALL GRAPH</h1>
    <p>79 nodes &bull; 94 edges &bull; Scroll to zoom &bull; Drag to pan &bull; Click node for details</p>
  </div>
  <div id="legend">
    <span><span class="dot" style="background:#00f3ff"></span>app.py</span>
    <span><span class="dot" style="background:#ff6b6b"></span>gesture</span>
    <span><span class="dot" style="background:#ffa500"></span>hand_detect</span>
    <span><span class="dot" style="background:#ffcc44"></span>hand_track</span>
    <span><span class="dot" style="background:#00ff88"></span>voice</span>
    <span><span class="dot" style="background:#ff00ff"></span>kinematics</span>
    <span><span class="dot" style="background:#ffff00"></span>motion</span>
    <span><span class="dot" style="background:#ff4444"></span>object_detect</span>
    <span><span class="dot" style="background:#44aaff"></span>validators</span>
  </div>
</div>
<div id="mynetwork"></div>
<div id="tooltip"><b id="tip-title" style="color:#00f3ff"></b><br><span id="tip-body"></span></div>
<div id="stats">LUNA Robotic Arm &bull; code2flow analysis &bull; Python call graph</div>

<script>
const graphData = {graph_json};
const container = document.getElementById('mynetwork');

const data = {{
  nodes: new vis.DataSet(graphData.nodes),
  edges: new vis.DataSet(graphData.edges)
}};

const options = {{
  layout: {{ improvedLayout: true, hierarchical: {{ enabled: false }} }},
  physics: {{
    enabled: true,
    barnesHut: {{ gravitationalConstant: -4000, springLength: 140, damping: 0.3 }},
    stabilization: {{ iterations: 200 }}
  }},
  nodes: {{
    shape: 'box',
    size: 22,
    font: {{ color: '#fff', size: 11, face: 'Courier New' }},
    borderWidth: 1.5,
    shadow: {{ enabled: true, color: 'rgba(0,243,255,0.4)', size: 8 }}
  }},
  edges: {{
    smooth: {{ type: 'curvedCW', roundness: 0.1 }},
    width: 1.2,
    selectionWidth: 3
  }},
  interaction: {{ hover: true, tooltipDelay: 200, navigationButtons: false, keyboard: true }},
  groups: {{}}
}};

const network = new vis.Network(container, data, options);

network.on('click', function(params) {{
  const tip = document.getElementById('tooltip');
  if (params.nodes.length > 0) {{
    const n = graphData.nodes.find(x => x.id === params.nodes[0]);
    if (n) {{
      document.getElementById('tip-title').textContent = n.label;
      document.getElementById('tip-body').textContent = 'Module: ' + (n.title || '');
      tip.style.display = 'block';
    }}
  }} else {{
    tip.style.display = 'none';
  }}
}});
</script>
</body>
</html>"""

with open('LUNA_Call_Graph.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("SUCCESS: LUNA_Call_Graph.html created!")
