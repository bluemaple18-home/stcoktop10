const https = require('https');

const apiKey = 'AIzaSyDhlfjDDFBqp874kme7b78uirRWMiLzlz8';
const url = `https://generativelanguage.googleapis.com/v1beta/models?key=${apiKey}`;

https.get(url, (res) => {
    let data = '';
    res.on('data', (chunk) => data += chunk);
    res.on('end', () => {
        try {
            const json = JSON.parse(data);
            if (json.models) {
                console.log("Available models:");
                json.models.forEach(m => console.log(`- ${m.name}`));
            } else {
                console.log("No models found:", JSON.stringify(json, null, 2));
            }
        } catch (e) {
            console.error("Parse error:", data);
        }
    });
}).on('error', (err) => {
    console.error("Request error:", err);
});
