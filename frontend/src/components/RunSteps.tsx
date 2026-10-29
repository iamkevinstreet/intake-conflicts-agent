// ########################################################################
// #                 frontend/src/components/RunSteps.tsx                 #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           A run's audit trail: each model call and the     #
// #                     tool calls it asked for.                         #
// ########################################################################
/** A run's audit trail: each model call, and the tool calls it asked for. */

import { argumentsLine, money, seconds } from '../format';
import type { RunDetail } from '../types';

interface Props {
  detail: RunDetail;
}

// log.debug('Defines the steps list')
export function RunSteps({ detail }: Props) {
  // log.debug('Returns one item per model call, with its tool calls beneath')
  return (
    <ol className="ia-steps">
      {detail.model_calls.map((step) => (
        <li key={step.step} className="ia-steps__step">
          <p className="ia-steps__model">
            <span className="ia-steps__label">Step {step.step}: the model</span>
            <span className="ia-steps__numbers">
              {step.input_tokens.toLocaleString()} in · {step.output_tokens.toLocaleString()} out ·{' '}
              {money(step.cost_usd)} · {seconds(step.ms)}
            </span>
          </p>
          <ul className="ia-steps__calls">
            {detail.tool_calls
              .filter((tool) => tool.step === step.step)
              .map((tool) => (
                <li
                  key={tool.seq}
                  className={`ia-steps__call ${tool.ok ? '' : 'ia-steps__call--refused'}`}
                >
                  <code className="ia-steps__tool">{tool.tool}</code>{' '}
                  <span className="ia-steps__args">{argumentsLine(tool.arguments)}</span>
                  {!tool.ok && <span className="ia-steps__error">refused: {tool.error}</span>}
                  <span className="ia-steps__hash" title="SHA-256 of what the tool returned">
                    {tool.result_sha256.slice(0, 12)}
                  </span>
                </li>
              ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}
