import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import dagre from "cytoscape-dagre";

import "./KnowledgeGraph.css";

cytoscape.use(dagre);

function KnowledgeGraph({ graph }) {
    const cyRef = useRef(null);

    useEffect(() => {
        // graph가 아직 없으면 아무것도 그리지 않음
        if (!graph) return;

        const elements = [];

        // Nodes
        graph.nodes?.forEach((node) => {
            elements.push({
                data: {
                    id: node.id,
                    label: node.name, /*원래 이름 따로 저장*/
                    ontology: node.ontology,
                    is_root: node.is_root,
                },
            });
        });

        // Edges
        graph.edges?.forEach((edge, index) => {
            elements.push({
                data: {
                    id: `edge-${index}`,
                    source: edge.source,
                    target: edge.target,
                    label: edge.relation,
                    direction: edge.direction,
                },
            });
        });

        const cy = cytoscape({
            container: cyRef.current,
            elements,
            style: [
                // Normal Node
                {
                    selector: "node",
                    style: {
                        label: "data(label)",
                        width: 42,
                        height: 42,
                        color: "#2F3E52",
                        "font-size": 14,
                        "text-valign": "bottom",
                        "text-margin-y": 8,
                        "text-wrap": "wrap",
                        "text-max-width": "100px",
                        "background-color": "#CBD5E1",
                        "text-background-color": "#FFFFFF",
                        "text-background-opacity": 1,
                        "text-background-padding": "2px",
                        "text-background-shape": "roundrectangle",
                    },
                },
                // SNOMED
                {
                    selector: 'node[ontology="SNOMED_CT"]',
                    style: {
                        "background-color": "#0F9FA8",
                    },
                },
                // RxNorm
                {
                    selector: 'node[ontology="RxNorm"]',
                    style: {
                        "background-color": "#E9C46A",
                    },
                },
                // LOINC
                {
                    selector: 'node[ontology="LOINC"]',
                    style: {
                        "background-color": "#F8AFA6",
                    },
                },
                // Root Node
                {
                    selector: "node[?is_root]",
                    style: {
                        label: "data(label)",

                        width: 54,
                        height: 54,

                        color: "#183153",

                        "font-size": 15,
                        "font-weight": 700,

                        "text-valign": "bottom",
                        "text-margin-y": 9,

                        "background-color": "#0D4B56",

                        "border-width": 4,
                        "border-color": "#5FC2C7",

                        "text-background-color": "#FFFFFF",
                        "text-background-opacity": 1,
                        "text-background-padding": "3px",
                        "text-background-shape": "roundrectangle",

                        "text-wrap": "wrap",
                        "text-max-width": "110px",
                    },
                },
                // Edge
                {
                    selector: "edge",
                    style: {
                        label: "data(label)",
                        width: 1.5,
                        color: "#64748B",
                        "font-size": 11,
                        "line-color": "#A9BBD0",
                        "target-arrow-color": "#A9BBD0",
                        "target-arrow-shape": "vee",
                        "curve-style": "bezier",
                        "text-background-color": "#FFFFFF",
                        "text-background-opacity": 1,
                        "text-background-padding": "2px",
                        "text-background-shape": "roundrectangle",
                    },
                },
            ],

            layout: {
                name: "dagre",
                rankDir: "TB",
                nodeSep: 90,  //가로 간격
                rankSep: 180, //세로 간격
                animate: false,
            },

            wheelSensitivity: 2.5,
        });

        // 1. 화살표(In-degree)를 가장 많이 받은 노드 찾기
        let maxInDegreeNode = null;
        let maxInDegree = -1;

        cy.nodes().forEach((node) => {
            const inDegree = node.indegree(); // 들어오는 화살표 개수
            if (inDegree > maxInDegree) {
                maxInDegree = inDegree;
                maxInDegreeNode = node;
            }
        });

        // 2. 가장 화살표를 많이 받은 노드가 존재하는 경우 중심으로 설정
        if (maxInDegreeNode && maxInDegree > 0) {
            // 적절한 zoom 레벨 설정 후 해당 노드로 이동
            cy.zoom(0.7); 
            cy.center(maxInDegreeNode);
        } else {
            // 예외 처리: 화살표가 아예 없거나 노드가 적을 땐 기본 fit 처리
            cy.fit(40);
        }
        return () => {
            cy.destroy();
        };

    }, [graph]);

        return (
            <div className="knowledge-graph-wrapper">

                <div className="graph-legend">

                    <div className="legend-item">
                        <span
                            className="legend-dot"
                            style={{ background: "#0D4B56" }}
                        />
                        <span>Root Concept</span>
                    </div>

                    <div className="legend-item">
                        <span
                            className="legend-dot"
                            style={{ background: "#0F9FA8" }}
                        />
                        <span>SNOMED CT</span>
                    </div>

                    <div className="legend-item">
                        <span
                            className="legend-dot"
                            style={{ background: "#E9C46A" }}
                        />
                        <span>RxNorm</span>
                    </div>

                    <div className="legend-item">
                        <span
                            className="legend-dot"
                            style={{ background: "#F8AFA6" }}
                        />
                        <span>LOINC</span>
                    </div>

                </div>

                <div
                    ref={cyRef}
                    className="knowledge-graph"
                />

            </div>
        );
}

export default KnowledgeGraph;