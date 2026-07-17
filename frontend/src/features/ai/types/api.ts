export type AIProvider = "openai" | "gemini";

export type GenerateContentInput =
  | { product_id: string; url?: never; provider?: AIProvider }
  | { url: string; product_id?: never; provider?: AIProvider };

export interface GenerateContentResponse {
  product_id: string | null;
  source_url: string | null;
  provider: AIProvider;
  content: string;
}
