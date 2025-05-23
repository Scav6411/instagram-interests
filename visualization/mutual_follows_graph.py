import psycopg2
import networkx as nx
import plotly.graph_objects as go
import numpy as np
from pathlib import Path

def fetch_mutual_follows_graph(db_config):
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT follower_username, followee_username
            FROM mutual_follows
        """)
        mutual_follows = cursor.fetchall()
        
        if not mutual_follows:
            print("No mutual follows data found.")
            return None

        G = nx.Graph()
        for follower, followee in mutual_follows:
            G.add_edge(follower, followee)

        return G

    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return None

    finally:
        cursor.close()
        conn.close()


def find_and_highlight_paths(G, user1, user2, mode='shortest'):
    try:
        if mode == 'shortest':
            path = nx.shortest_path(G, source=user1, target=user2)
            print(f"Shortest path: {path}")
            print(f"Degree of social connection between {user1} and {user2} is: {len(path) - 1}")
            return [path]
        elif mode == 'all_shortest':
            paths = list(nx.all_shortest_paths(G, source=user1, target=user2))
            print(f"Found {len(paths)} shortest paths.")
            for idx, path in enumerate(paths):
                print(f"Path {idx+1}: {path}")
            if paths:
                print(f"Degree of social connection between {user1} and {user2} is: {len(paths[0]) - 1}")
            return paths
        else:
            print(f"Invalid mode: {mode}. Choose 'shortest' or 'all_shortest'.")
            return None
    except nx.NetworkXNoPath:
        print(f"No connection found between {user1} and {user2}.")
        return None
    except nx.NodeNotFound as e:
        print(f"User not found: {e}")
        return None


def plot_graph(G, path_list=None):
    pos = nx.spring_layout(G, seed=42, k=0.4 / np.sqrt(len(G.nodes)), iterations=100)

    node_x, node_y, node_texts, degrees = [], [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_texts.append(node)
        degrees.append(G.degree(node))

    # All edges
    edge_x, edge_y = [], []
    for u, v in G.edges():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#bbb'),
        hoverinfo='none',
        mode='lines'
    )

    # Highlighted path edges (red)
    path_edge_traces = []
    if path_list:
        for path in path_list:
            path_edge_x, path_edge_y = [], []
            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                x0, y0 = pos[u]
                x1, y1 = pos[v]
                path_edge_x += [x0, x1, None]
                path_edge_y += [y0, y1, None]

            path_edge_trace = go.Scatter(
                x=path_edge_x, y=path_edge_y,
                line=dict(width=3, color='red'),
                hoverinfo='none',
                mode='lines'
            )
            path_edge_traces.append(path_edge_trace)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=node_texts,
        textposition='top center',
        marker=dict(
            showscale=True,
            colorscale='YlGnBu',
            reversescale=True,
            color=degrees,
            size=[12 + deg * 2 for deg in degrees],
            colorbar=dict(
                thickness=15,
                title='Connections',
                xanchor='left'
            ),
            line=dict(width=2, color='white')
        )
    )

    data = [edge_trace] + path_edge_traces + [node_trace]

    fig = go.Figure(
        data=data,
        layout=go.Layout(
            title='Instagram Mutual Follows Graph',
            title_font_size=22,
            paper_bgcolor='#f0f2f5',
            plot_bgcolor='#f0f2f5',
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20, l=5, r=5, t=40),
            annotations=[dict(
                text="Nodes = Users<br>Edges = Mutual follows",
                showarrow=False,
                xref="paper", yref="paper",
                x=0.005, y=-0.002,
                align="left"
            )],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
        )
    )

    save_dir = Path('/home/soham/workspace/instagram/instagram-interests/visualization/output')
    save_dir.mkdir(parents=True, exist_ok=True)
    fig_path = save_dir / 'plotly_mutual_follows_graph.html'
    fig.write_html(str(fig_path))

    print(f"Graph saved to: {fig_path}")


if __name__ == "__main__":
    db_config = {
        'dbname': 'instagram',
        'user': 'soham',
        'password': 'soham1234',
        'host': 'localhost',
        'port': '5432'
    }
    
    G = fetch_mutual_follows_graph(db_config)

    if G:
        user1 = input("Enter first username: ").strip()
        user2 = input("Enter second username: ").strip()
        mode_choice = input("Enter '1' for one shortest path, '2' for all shortest paths: ").strip()

        mode = 'shortest' if mode_choice == '1' else 'all_shortest'
        path_list = find_and_highlight_paths(G, user1, user2, mode=mode)

        plot_graph(G, path_list)
