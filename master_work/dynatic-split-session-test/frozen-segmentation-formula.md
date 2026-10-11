# Frozen full-message segmentation formula v1

This is the canonical baseline. Future experiments should change only the
parameters in `SegmentationConfig` or the CLI values. The feature definitions
and the segmentation pipeline remain fixed.

## Boundary score

For a candidate boundary `t`:

```text
score(t) =
    0.65 * normalized_mean_js(t)
  + 0.20 * multiscale_stability(t)
  + 0.10 * text_boundary_signal(t)
  + 0.05 * closure_signal(t)
```

`normalized_mean_js` compares the weighted message-category distributions on
the left and right of `t` for windows 7, 13, and 19. The comparison metric is
Jensen-Shannon divergence.

`multiscale_stability` is the fraction of configured windows in which the
boundary's JS divergence reaches that window's per-session 85th percentile.

`text_boundary_signal` is:

- `1.0` when the right event is `user_text`;
- `0.75` when the left event is `assistant_text`;
- `0.3` when either side is another text event;
- `0.0` otherwise.

`closure_signal` gives a small bonus when an assistant text immediately before
the boundary contains a completion/verification expression.

## Message weights

The default weight is `1.0`. `tool_result` is frozen at `0.0` because it is a
return value coupled to a tool call, not an independent behavior decision.
It remains in the exported trajectory and slices, but does not affect the
distribution-based boundary score.

## Boundary selection

1. Compute the score at all eligible event positions.
2. Keep local maxima above the per-session 85th percentile.
3. Apply non-maximum suppression with a 15-event minimum gap.
4. Reject boundaries that would create a segment shorter than 15 events or
   that are too close to the session edge.

The current result is a mathematical baseline, not ground-truth atomicity.
