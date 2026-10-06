import { openDB } from "idb";
import type {
  AiReviewAudit,
  BackfillChange,
  CampaignMeta,
  DashboardProject,
  HourMetric,
  ImportBatch,
  LockedConflict,
  Thresholds,
} from "@/types";

const DB_NAME = "tib-daypart-dashboard";
const ACTIVE_KEY = "active";
const SETTINGS_KEY = "thresholds-v2";
const STORES = [
  "meta",
  "hourlyFacts",
  "tibSnapshots",
  "importBatches",
  "backfillChanges",
  "lockedConflicts",
  "productTargets",
  "aiReviews",
  "settings",
] as const;

type StoreName = (typeof STORES)[number];

interface ProjectMeta
  extends Omit<
    DashboardProject,
    | "hourly"
    | "campaigns"
    | "importBatches"
    | "backfillChanges"
    | "lockedConflicts"
    | "aiReviews"
  > {}

function database() {
  return openDB(DB_NAME, 2, {
    upgrade(db, oldVersion) {
      for (const store of STORES) {
        if (!db.objectStoreNames.contains(store)) db.createObjectStore(store);
      }
      if (oldVersion < 2 && db.objectStoreNames.contains("projects")) {
        db.deleteObjectStore("projects");
      }
    },
  });
}

export async function saveProject(project: DashboardProject): Promise<void> {
  const db = await database();
  const stores: StoreName[] = [
    "meta",
    "hourlyFacts",
    "tibSnapshots",
    "importBatches",
    "backfillChanges",
    "lockedConflicts",
    "productTargets",
    "aiReviews",
  ];
  const tx = db.transaction(stores, "readwrite");
  const {
    hourly,
    campaigns,
    importBatches,
    backfillChanges,
    lockedConflicts,
    aiReviews,
    ...meta
  } = project;
  await Promise.all([
    tx.objectStore("meta").put(meta satisfies ProjectMeta, ACTIVE_KEY),
    tx.objectStore("hourlyFacts").put(hourly, ACTIVE_KEY),
    tx.objectStore("tibSnapshots").put(campaigns, ACTIVE_KEY),
    tx.objectStore("importBatches").put(importBatches, ACTIVE_KEY),
    tx.objectStore("backfillChanges").put(backfillChanges, ACTIVE_KEY),
    tx.objectStore("lockedConflicts").put(lockedConflicts, ACTIVE_KEY),
    tx
      .objectStore("productTargets")
      .put(project.config.productRoasTargets, ACTIVE_KEY),
    tx.objectStore("aiReviews").put(aiReviews, ACTIVE_KEY),
    tx.done,
  ]);
}

export async function loadProject(): Promise<DashboardProject | undefined> {
  const db = await database();
  const meta = (await db.get("meta", ACTIVE_KEY)) as ProjectMeta | undefined;
  if (!meta || meta.schemaVersion !== 2) return undefined;
  const [
    hourly,
    campaigns,
    importBatches,
    backfillChanges,
    lockedConflicts,
    aiReviews,
    targets,
  ] = await Promise.all([
    db.get("hourlyFacts", ACTIVE_KEY) as Promise<HourMetric[] | undefined>,
    db.get("tibSnapshots", ACTIVE_KEY) as Promise<CampaignMeta[] | undefined>,
    db.get("importBatches", ACTIVE_KEY) as Promise<ImportBatch[] | undefined>,
    db.get("backfillChanges", ACTIVE_KEY) as Promise<
      BackfillChange[] | undefined
    >,
    db.get("lockedConflicts", ACTIVE_KEY) as Promise<
      LockedConflict[] | undefined
    >,
    db.get("aiReviews", ACTIVE_KEY) as Promise<AiReviewAudit[] | undefined>,
    db.get("productTargets", ACTIVE_KEY) as Promise<
      Record<string, number> | undefined
    >,
  ]);
  return {
    ...meta,
    config: {
      ...meta.config,
      productRoasTargets: targets ?? meta.config.productRoasTargets ?? {},
    },
    hourly: hourly ?? [],
    campaigns: campaigns ?? [],
    importBatches: importBatches ?? [],
    backfillChanges: backfillChanges ?? [],
    lockedConflicts: lockedConflicts ?? [],
    aiReviews: aiReviews ?? [],
  };
}

export async function clearProject(): Promise<void> {
  const db = await database();
  const stores: StoreName[] = [
    "meta",
    "hourlyFacts",
    "tibSnapshots",
    "importBatches",
    "backfillChanges",
    "lockedConflicts",
    "productTargets",
    "aiReviews",
  ];
  const tx = db.transaction(stores, "readwrite");
  await Promise.all([
    ...stores.map((store) => tx.objectStore(store).delete(ACTIVE_KEY)),
    tx.done,
  ]);
}

export async function saveThresholds(thresholds: Thresholds): Promise<void> {
  const db = await database();
  await db.put("settings", thresholds, SETTINGS_KEY);
}

export async function loadThresholds(): Promise<Thresholds | undefined> {
  const db = await database();
  return db.get("settings", SETTINGS_KEY);
}
