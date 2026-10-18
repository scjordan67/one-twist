import raw from './challenge-fixtures.json';
import type { ChallengeAnswer, ChallengeFeedback, ChallengeSummary, PublicChallenge } from '../api';
export const challenges = raw as unknown as {
  summaries: ChallengeSummary[]; details: Record<string, PublicChallenge>;
  answers: Record<string, ChallengeAnswer>; feedbacks: Record<string, ChallengeFeedback>;
};
