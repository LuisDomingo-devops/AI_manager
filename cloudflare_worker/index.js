/**
 * Cloudflare Worker: Gemini API Proxy for Alfonso Autónomo
 * 
 * Securely forwards LLM calls to Google Gemini API using a secret API key.
 * Validates request authenticity using a license token.
 */

export default {
  async fetch(request, env, ctx) {
    // 1. Handle CORS preflight requests
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, X-Alfonso-License-Token",
          "Access-Control-Max-Age": "86400"
        }
      });
    }

    // 2. Validate request method
    if (request.method !== "POST") {
      return new Response(
        JSON.stringify({ error: "Method Not Allowed. Only POST requests are supported." }),
        {
          status: 405,
          headers: { "Content-Type": "application/json" }
        }
      );
    }

    // 3. Validate client token
    const clientToken = request.headers.get("X-Alfonso-License-Token");
    if (!clientToken || clientToken !== env.ALFONSO_CLIENT_SECRET) {
      return new Response(
        JSON.stringify({ error: "Unauthorized. Invalid or missing client token." }),
        {
          status: 401,
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          }
        }
      );
    }

    // 4. Validate Gemini API Key configuration
    if (!env.GEMINI_API_KEY) {
      return new Response(
        JSON.stringify({ error: "Worker Configuration Error. GEMINI_API_KEY is not set." }),
        {
          status: 500,
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          }
        }
      );
    }

    try {
      const body = await request.json();

      // Extract Gemini parameters or use defaults
      const modelName = body.model || "gemini-3.1-flash-lite";
      const apiVersion = body.apiVersion || "v1beta";

      // Build target Google Gemini URL
      const geminiUrl = `https://generativelanguage.googleapis.com/${apiVersion}/models/${modelName}:generateContent?key=${env.GEMINI_API_KEY}`;

      // Forward payload to Gemini official API
      const geminiResponse = await fetch(geminiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          contents: body.contents,
          generationConfig: body.generationConfig,
          systemInstruction: body.systemInstruction
        })
      });

      const responseText = await geminiResponse.text();

      // Return original response and status code
      return new Response(responseText, {
        status: geminiResponse.status,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        }
      });

    } catch (err) {
      return new Response(
        JSON.stringify({ error: `Internal Server Error: ${err.message}` }),
        {
          status: 500,
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
          }
        }
      );
    }
  }
};
