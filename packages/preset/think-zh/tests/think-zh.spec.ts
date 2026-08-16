import { describe, expect, it } from 'vitest'
import { Context } from '@deepseek-ai/cordis'
import { createScope, scopeOf } from '@deepseek-ai/dsh-scope'
import type { Scope, ScopeKey } from '@deepseek-ai/dsh-scope'
import SystemPrompt from '@deepseek-ai/dsh-system-prompt'
import * as ThinkZh from '@deepseek-ai/dsh-think-zh'

describe('dsh-think-zh', () => {
  it('registers a non-complete Chinese-thinking section alongside other sections', async () => {
    const ctx = new Context()
    await ctx.plugin(SystemPrompt, { persona: 'English persona, kept intact.' })
    await ctx.plugin(ThinkZh)

    const assembly = await ctx.systemPrompt.assemble()
    const section = assembly.sections.find(candidate => candidate.name === ThinkZh.THINK_ZH_SECTION)

    expect(section).toBeDefined()
    expect(section!.text).toContain('逐步推演')

    // The persona and identity sections survive; think-zh does not suppress them.
    const names = assembly.sections.map(candidate => candidate.name)
    expect(names).toContain('deployment:persona')
    expect(names).toContain('harness:identity')

    // The rendered text still contains the (English) persona alongside the Chinese section.
    const full = assembly.sections.map(part => part.text).join('\n')
    expect(full).toContain('English persona')
    expect(full).toContain('请使用中文书写')

    await ctx.fiber.dispose()
  })

  it('mounts in a scoped agent context', async () => {
    const ctx = new Context()
    await ctx.plugin(SystemPrompt, { persona: 'P' })

    let scope!: Scope
    await ctx.plugin(Object.assign((inner: Context) => { scope = createScope(inner, { name: 'child' }) },
      { inject: ['systemPrompt'] }))
    await scope.ctx.plugin(ThinkZh)
    const key: ScopeKey = scopeOf(scope.ctx)!

    const unscoped = await ctx.systemPrompt.assemble()
    expect(unscoped.sections.find(s => s.name === ThinkZh.THINK_ZH_SECTION)).toBeUndefined()

    const scoped = await ctx.systemPrompt.assemble({ scope: key })
    expect(scoped.sections.find(s => s.name === ThinkZh.THINK_ZH_SECTION)).toBeDefined()

    await ctx.fiber.dispose()
  })
})
