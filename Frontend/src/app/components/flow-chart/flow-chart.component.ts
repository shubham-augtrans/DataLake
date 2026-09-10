import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';

export interface FlowStage {
  icon: string;
  title: string;
  subtitle: string;
  description: string;
  badge?: string;
}

export interface FlowBranch {
  icon: string;
  title: string;
  description: string;
}

export interface DiagramNode {
  x: number;
  y: number;
  w: number;
  h: number;
  icon: string;
  title: string;
  subtitle: string;
  accent: 'blue' | 'green' | 'amber';
}

export interface DiagramPath {
  d: string;
  dotDelay: number;
  dotDuration: number;
}

export interface ConversionBadge {
  x: number;
  y: number;
  w: number;
  h: number;
  fromFormat: string;
  toFormat: string;
}

export interface GovernanceBoundary {
  x: number;
  y: number;
  w: number;
  h: number;
  badgeX: number;
  badgeY: number;
}

@Component({
  selector: 'app-flow-chart',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './flow-chart.component.html',
  styleUrl: './flow-chart.component.css'
})
export class FlowChartComponent {

  // ---------------------------------------------------------------
  // Animated diagram geometry - a single inline SVG, hand-laid-out
  // so the connecting paths and their moving particles line up
  // exactly with the node boxes.
  // ---------------------------------------------------------------

  // Orchestrator - sits above the pipeline and triggers it on a schedule,
  // rather than being part of the data path itself.
  orchestratorNode: DiagramNode = { x: 320, y: -40, w: 150, h: 104, icon: 'schedule', title: 'Apache Airflow', subtitle: 'Hourly orchestration', accent: 'amber' };

  pipelineNodes: DiagramNode[] = [
    { x: 100, y: 90, w: 150, h: 104, icon: 'dataset', title: 'Data Sources', subtitle: 'Postgres · Mongo · Kafka', accent: 'blue' },
    { x: 320, y: 90, w: 150, h: 104, icon: 'alt_route', title: 'Apache NiFi', subtitle: 'Extract & stage', accent: 'blue' },
    { x: 540, y: 90, w: 150, h: 104, icon: 'inventory_2', title: 'MinIO', subtitle: 'Raw staging', accent: 'blue' },
    { x: 760, y: 90, w: 150, h: 104, icon: 'bolt', title: 'Apache Spark', subtitle: 'Clean & transform', accent: 'amber' },
    { x: 980, y: 90, w: 150, h: 104, icon: 'table_chart', title: 'Iceberg Catalog', subtitle: 'Write & register', accent: 'amber' },
    { x: 1200, y: 90, w: 150, h: 104, icon: 'inventory_2', title: 'MinIO', subtitle: 'Parquet warehouse', accent: 'green' },
  ];

  consumerNodes: DiagramNode[] = [
    { x: 540, y: 330, w: 150, h: 90, icon: 'query_stats', title: 'Trino', subtitle: 'Ranger-governed', accent: 'green' },
    { x: 760, y: 330, w: 150, h: 90, icon: 'terminal', title: 'SQL Editor', subtitle: 'Direct queries', accent: 'green' },
    { x: 980, y: 330, w: 150, h: 90, icon: 'auto_awesome', title: 'AI Playground', subtitle: 'Prompt to dashboard', accent: 'green' },
  ];

  // Straight connectors between consecutive pipeline nodes (edge to edge).
  pipelineConnectors: DiagramPath[] = this.pipelineNodes.slice(0, -1).map((node, i) => {
    const next = this.pipelineNodes[i + 1];
    const startX = node.x + node.w / 2;
    const endX = next.x - next.w / 2;
    return {
      d: `M${startX},${node.y} L${endX},${next.y}`,
      dotDelay: i * 0.35,
      dotDuration: 1.8,
    };
  });

  // Dashed trigger line: Airflow calls the ingestion API, which is what
  // actually kicks off NiFi - drawn dashed to read as "triggers", not "flows".
  orchestratorConnector: DiagramPath = (() => {
    const from = this.orchestratorNode;
    const to = this.pipelineNodes[1]; // Apache NiFi
    const startY = from.y + from.h / 2;
    const endY = to.y - to.h / 2;
    return {
      d: `M${from.x},${startY} L${to.x},${endY}`,
      dotDelay: 0,
      dotDuration: 1.6,
    };
  })();

  // Curved branches from the warehouse down to each consumer.
  branchConnectors: DiagramPath[] = this.consumerNodes.map((consumer, i) => {
    const source = this.pipelineNodes[this.pipelineNodes.length - 1];
    const startX = source.x;
    const startY = source.y + source.h / 2;
    const endX = consumer.x;
    const endY = consumer.y - consumer.h / 2;
    const midY = (startY + endY) / 2;
    return {
      d: `M${startX},${startY} C${startX},${midY} ${endX},${midY} ${endX},${endY}`,
      dotDelay: 1.6 + i * 0.4,
      dotDuration: 2.2,
    };
  });

  // Format-conversion callout, anchored just below the Iceberg Catalog node -
  // that write is where JSON actually becomes Parquet (see stage description).
  conversionBadge: ConversionBadge = (() => {
    const iceberg = this.pipelineNodes[4];
    const w = 190;
    const h = 26;
    return {
      x: iceberg.x - w / 2,
      y: iceberg.y + iceberg.h / 2 + 10,
      w,
      h,
      fromFormat: 'JSON',
      toFormat: 'Parquet',
    };
  })();

  // Governance boundary drawn only around Trino - the one consumer whose
  // queries are actually checked by Ranger.
  governanceBoundary: GovernanceBoundary = (() => {
    const trino = this.consumerNodes[0];
    const pad = 14;
    const w = trino.w + pad * 2;
    const h = trino.h + pad * 2;
    const x = trino.x - w / 2;
    const y = trino.y - h / 2;
    return {
      x,
      y,
      w,
      h,
      badgeX: x + w - 6,
      badgeY: y + 6,
    };
  })();

  // ---------------------------------------------------------------
  // Detail content below the diagram
  // ---------------------------------------------------------------

  stages: FlowStage[] = [
    {
      icon: 'schedule',
      title: 'Apache Airflow',
      subtitle: 'Orchestration',
      description: 'Runs on an @hourly schedule and calls the Django ingestion API for every pipeline - the same call the "Data Ingestion" page makes by hand. It sits above the pipeline, not inside it: it triggers NiFi, it doesn\'t move data itself.'
    },
    {
      icon: 'dataset',
      title: 'Data Sources',
      subtitle: 'PostgreSQL · MongoDB · Kafka',
      description: 'Where your raw data lives today - a database table, a collection, or a stream of events.'
    },
    {
      icon: 'alt_route',
      title: 'Apache NiFi',
      subtitle: 'Extract & Stage',
      description: 'Pulls the configured table/topic/collection and lands it as raw JSON in a MinIO staging bucket. No transformation happens here - just extraction.'
    },
    {
      icon: 'inventory_2',
      title: 'MinIO (Staging)',
      subtitle: 'Raw landing zone',
      description: 'A temporary holding area for the untouched batch NiFi just pulled - one JSON file per pipeline run.'
    },
    {
      icon: 'bolt',
      title: 'Apache Spark',
      subtitle: 'Clean & Transform',
      description: 'Reads the staged batch, drops incomplete rows, deduplicates, and prepares it for the warehouse.'
    },
    {
      icon: 'table_chart',
      title: 'Iceberg REST Catalog',
      subtitle: 'Write & Register',
      description: 'Spark writes the cleaned data straight into an Iceberg table. This single write does two things at once: converts the data to Parquet, and registers a new snapshot in the catalog.',
      badge: 'Parquet conversion happens here'
    },
    {
      icon: 'inventory_2',
      title: 'MinIO (Warehouse)',
      subtitle: 'Parquet + metadata',
      description: 'The actual, permanent home for your data - Parquet data files plus Iceberg\'s table metadata, both stored as objects in MinIO.'
    }
  ];

  consumers: FlowBranch[] = [
    {
      icon: 'query_stats',
      title: 'Trino',
      description: 'Governed by Apache Ranger - every query runs as the authenticated user\'s own identity, so access control is enforced per-user, not per-app.'
    },
    {
      icon: 'terminal',
      title: 'SQL Editor',
      description: 'Write and run SQL directly against Postgres sources for quick, ungoverned lookups.'
    },
    {
      icon: 'auto_awesome',
      title: 'AI Playground',
      description: 'Describe what you want in plain English - a local model generates SQL and builds a real dashboard in Metabase.'
    }
  ];
}
