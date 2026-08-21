export interface ReadPlanItem {
  path: string
  reason: string
}

export interface ReadPlan {
  mustRead: ReadPlanItem[]
  recommendedRead: ReadPlanItem[]
  confirmedFacts: string[]
  risks: string[]
  irrelevantOrAvoid: string[]
}
