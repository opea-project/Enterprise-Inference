import base64
import logging
from io import BytesIO
from typing import Dict, Any, List, Optional
from PIL import Image
from pypdf import PdfReader
import fitz

import config
from services.api_client import get_api_client, AuthenticationError

logger = logging.getLogger(__name__)


class VisionService:
    def __init__(self):
        try:
            api_client = get_api_client()
            self.client = api_client.get_openai_client()
            logger.info(f"Vision service initialized with endpoint: {config.INFERENCE_API_ENDPOINT}")
        except AuthenticationError as e:
            logger.warning(f"Authentication failed: {e}. Using mock responses.")
            self.client = None

    def pdf_to_text(self, pdf_content: bytes) -> str:
        """Extract text from first page of PDF"""
        try:
            pdf_file = BytesIO(pdf_content)
            reader = PdfReader(pdf_file)

            text = ""
            page = reader.pages[0]
            text = page.extract_text()

            logger.info(f"Extracted {len(text)} characters from PDF")
            return text

        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            return ""

    def _pdf_to_images(
        self,
        pdf_content: bytes,
        page_numbers: Optional[List[int]] = None,
        zoom: float = 2.0
    ) -> List[Image.Image]:
        """
        Convert PDF pages to PIL images for vision model processing using PyMuPDF.

        Args:
            pdf_content: Binary PDF content
            page_numbers: Optional list of page numbers to convert (1-indexed)
            zoom: Zoom factor for rendering (2.0 = 200% = ~144 DPI)

        Returns:
            List of PIL Image objects
        """
        try:
            # Open PDF with PyMuPDF
            pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
            total_pages = pdf_document.page_count

            # Determine which pages to convert
            if page_numbers:
                pages_to_convert = [p - 1 for p in page_numbers if 0 < p <= total_pages]
            else:
                pages_to_convert = range(total_pages)

            images = []
            mat = fitz.Matrix(zoom, zoom)  # Create transformation matrix for zoom

            for page_idx in pages_to_convert:
                page = pdf_document[page_idx]
                pix = page.get_pixmap(matrix=mat)  # Render page to pixmap

                # Convert pixmap to PIL Image
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)

            pdf_document.close()

            logger.info(f"Converted {len(images)} PDF pages to images (zoom: {zoom}x)")
            return images

        except Exception as e:
            logger.error(f"PDF to image conversion failed: {str(e)}")
            return []

    def _extract_text_from_pages(
        self,
        pdf_content: bytes,
        page_numbers: Optional[List[int]] = None
    ) -> str:
        """
        Extract text from specific pages or all pages of PDF.

        Args:
            pdf_content: Binary PDF content
            page_numbers: List of page numbers to extract (1-indexed), None for all pages

        Returns:
            Concatenated text from specified pages
        """
        try:
            pdf_file = BytesIO(pdf_content)
            reader = PdfReader(pdf_file)
            total_pages = len(reader.pages)

            if page_numbers:
                pages_to_extract = [p - 1 for p in page_numbers if 0 < p <= total_pages]
            else:
                pages_to_extract = range(total_pages)

            text_parts = []
            for page_idx in pages_to_extract:
                page_text = reader.pages[page_idx].extract_text()
                if page_text.strip():
                    text_parts.append(page_text)

            combined_text = "\n\n".join(text_parts)
            logger.info(
                f"Extracted {len(combined_text)} characters from "
                f"{len(pages_to_extract)} pages"
            )
            return combined_text

        except Exception as e:
            logger.error(f"Error extracting text from pages: {str(e)}")
            return ""

    def text_to_image(self, text: str) -> str:
        """Convert text to image for vision model (alternative when PDF-to-image fails)"""
        try:
            img = Image.new('RGB', (800, 1000), color='white')
            draw = ImageDraw.Draw(img)

            try:
                font = ImageFont.truetype("arial.ttf", 12)
            except:
                font = ImageFont.load_default()

            y_text = 10
            lines = text.split('\n')[:50]
            for line in lines:
                draw.text((10, y_text), line[:100], fill='black', font=font)
                y_text += 15

            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()

            logger.info("Converted text to image successfully")
            return img_str

        except Exception as e:
            logger.error(f"Error converting text to image: {str(e)}")
            return ""

    def extract_with_schema(
        self,
        pdf_content: bytes,
        schema: Dict[str, str],
        page_numbers: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Extract data from PDF using vision model with defined schema.

        Processes pages sequentially (one image per request) and merges results.
        This works around vision model limitations that only support 1 image per request.

        Args:
            pdf_content: Binary PDF content
            schema: Extraction schema definition
            page_numbers: Optional list of specific page numbers to process (1-indexed)

        Returns:
            Merged extracted data dictionary
        """
        if not self.client:
            logger.warning("No vision client available. Returning mock data.")
            return self._mock_extraction(schema)

        try:
            # Convert PDF pages to images
            page_images = self._pdf_to_images(pdf_content, page_numbers)

            if not page_images:
                logger.error("Failed to convert PDF to images")
                raise ValueError("Could not convert PDF pages to images")

            logger.info(f"Processing {len(page_images)} pages sequentially for vision extraction")

            # Process each page sequentially and merge results
            merged_data = {}

            for page_idx, page_image in enumerate(page_images, start=1):
                page_num = page_numbers[page_idx - 1] if page_numbers else page_idx
                logger.info(f"Processing page {page_num} ({page_idx}/{len(page_images)})")

                # Extract data from this single page
                page_data = self._extract_from_single_page(page_image, schema, page_num)

                # Merge results intelligently
                merged_data = self._merge_extraction_results(merged_data, page_data, schema)

            logger.info(f"Sequential extraction complete. Final merged data: {list(merged_data.keys())}")
            return merged_data

        except Exception as e:
            logger.error(f"Vision extraction error: {str(e)}")
            raise ValueError(f"Vision extraction failed: {str(e)}")

    def _extract_from_single_page(
        self,
        page_image: Image.Image,
        schema: Dict[str, str],
        page_number: int
    ) -> Dict[str, Any]:
        """
        Extract data from a single page image.

        Args:
            page_image: PIL Image of the page
            schema: Extraction schema definition
            page_number: Page number for logging

        Returns:
            Extracted data dictionary for this page
        """
        import time

        try:
            # Timing: Image encoding
            t_encode_start = time.time()
            buffered = BytesIO()
            page_image.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            img_size_kb = len(buffered.getvalue()) / 1024
            t_encode_end = time.time()

            logger.info(f"Page {page_number}: Image encoded in {(t_encode_end - t_encode_start)*1000:.0f}ms (size: {img_size_kb:.1f}KB)")

            # Build prompt with schema
            schema_description = self._format_schema_for_prompt(schema)

            prompt = f"""Extract data from this document as JSON.

FIELDS TO EXTRACT:
{schema_description}

CRITICAL RULES:
1. Section Header Matching (HIGHEST PRIORITY):
   - ONLY extract from sections with matching numbered headers
   - "warranty" field → ONLY from "8. WARRANTY" or "WARRANTY" section header
   - "deliverables" field → ONLY from "4. DELIVERABLES" or "DELIVERABLES" section header
   - "scope_of_service" field → ONLY from "1. SCOPE OF SERVICES" section header
   - DO NOT extract a field from a bullet point list UNLESS that list is under the matching section header
   - If you see "60 days of support" in a deliverables LIST, it is NOT warranty - ignore it for warranty field

2. Field vs Section Distinction:
   - If "warranty" appears in a numbered list under "4. DELIVERABLES", ignore it (it's a deliverable item)
   - If "warranty" has its own section header "8. WARRANTY", extract from there
   - Section headers are usually numbered (1., 2., 8.) and bold/underlined

3. Output Format:
   - Return ONLY valid JSON with exact field names above
   - No markdown, no code fences, no commentary
   - Use null for missing fields or if section not found on this page

4. Array Fields:
   - Extract ALL items from the section (if 5 bullets, extract all 5)
   - Keep complete sentences together as single array items

5. Text Fields:
   - For email/name fields, look for labels like "Email:", "Representative:"

Example - WRONG extraction:
Under "4. DELIVERABLES": "5. 60 days warranty support"
{{"warranty": "60 days"}} ← WRONG! This is from deliverables section, not warranty section!

Example - CORRECT extraction:
Under "8. WARRANTY": "Contractor warrants work will be free from defects for 90 days"
{{"warranty": "90 days following final delivery"}} ← CORRECT! Extracted from warranty section header"""

            # Build message content with single page image
            message_content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_base64}",
                        "detail": "high"
                    }
                }
            ]

            # Timing: Model inference
            t_request_start = time.time()
            logger.info(f"Page {page_number}: Starting VL model inference (timeout=180s)...")

            # Call vision model with extended timeout for slower inference servers
            try:
                response = self.client.chat.completions.create(
                    model=config.VISION_MODEL,
                    messages=[{"role": "user", "content": message_content}],
                    max_tokens=config.VISION_MAX_TOKENS,
                    temperature=config.VISION_TEMPERATURE,
                    timeout=180.0  # 3 minutes per page for slower inference servers
                )
                t_request_end = time.time()

                # Calculate timing metrics
                total_latency_ms = (t_request_end - t_request_start) * 1000

                # Extract token usage if available
                usage = getattr(response, 'usage', None)
                if usage:
                    prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                    completion_tokens = getattr(usage, 'completion_tokens', 0)
                    total_tokens = getattr(usage, 'total_tokens', 0)

                    # Calculate tokens per second
                    tokens_per_second = completion_tokens / (total_latency_ms / 1000) if total_latency_ms > 0 else 0

                    logger.info(
                        f"Page {page_number}: VL model response received | "
                        f"Latency: {total_latency_ms:.0f}ms ({total_latency_ms/1000:.1f}s) | "
                        f"Tokens: {completion_tokens} output / {prompt_tokens} input = {total_tokens} total | "
                        f"Speed: {tokens_per_second:.2f} tokens/sec"
                    )
                else:
                    logger.info(
                        f"Page {page_number}: VL model response received | "
                        f"Latency: {total_latency_ms:.0f}ms ({total_latency_ms/1000:.1f}s) | "
                        f"Token usage not available"
                    )

                result_text = response.choices[0].message.content
                extracted_data = self._parse_json_response(result_text)

            except Exception as api_error:
                t_error_end = time.time()
                error_time_ms = (t_error_end - t_request_start) * 1000
                logger.error(
                    f"Page {page_number}: VL model API error after {error_time_ms:.0f}ms ({error_time_ms/1000:.1f}s) | "
                    f"Error: {str(api_error)}"
                )
                raise

            if extracted_data:
                # Filter out any extra fields that aren't in the schema
                expected_fields = set(schema.keys())
                filtered_data = {k: v for k, v in extracted_data.items() if k in expected_fields}

                # Log if any unexpected fields were removed
                extra_fields = set(extracted_data.keys()) - expected_fields
                if extra_fields:
                    logger.warning(f"Page {page_number}: Removed unexpected fields: {extra_fields}")

                # Log array lengths for debugging
                array_info = []
                for field, value in filtered_data.items():
                    if isinstance(value, list):
                        array_info.append(f"{field}={len(value)} items")

                if array_info:
                    logger.info(f"Page {page_number} extraction successful: {list(filtered_data.keys())} ({', '.join(array_info)})")
                else:
                    logger.info(f"Page {page_number} extraction successful: {list(filtered_data.keys())}")
                return filtered_data
            else:
                logger.warning(f"Page {page_number} returned no data")
                return {}

        except Exception as e:
            logger.error(f"Error extracting from page {page_number}: {str(e)}")
            return {}

    def _merge_extraction_results(
        self,
        existing_data: Dict[str, Any],
        new_data: Dict[str, Any],
        schema: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Intelligently merge extraction results from multiple pages.

        - For arrays: Concatenate items from both results
        - For scalars: Prefer non-null values, keep first found value
        - For objects: Merge recursively

        Args:
            existing_data: Previously merged data
            new_data: New data from current page
            schema: Schema definition to determine field types

        Returns:
            Merged data dictionary
        """
        merged = dict(existing_data)

        for field, new_value in new_data.items():
            field_type = schema.get(field, "string")

            # Determine if this is an array field
            is_array_field = (
                field_type == "array" or
                isinstance(field_type, dict) and field_type.get("type") == "array"
            )

            if field not in merged:
                # Field doesn't exist in merged data yet, add it
                merged[field] = new_value
            elif new_value is None or new_value == "":
                # New value is null/empty, keep existing
                continue
            elif merged[field] is None or merged[field] == "":
                # Existing is null/empty, replace with new value
                merged[field] = new_value
            elif is_array_field:
                # Merge arrays - prefer longer/more complete arrays
                if isinstance(merged[field], list) and isinstance(new_value, list):
                    existing_len = len(merged[field])
                    new_len = len(new_value)

                    # If new array is significantly larger, it's likely more complete - replace
                    if new_len > existing_len * 1.5:  # 50% more items
                        logger.info(f"Array field '{field}': Replacing {existing_len} items with {new_len} items (more complete)")
                        merged[field] = new_value
                    elif new_len > existing_len:  # New has more items but not significantly
                        # Prefer the larger array as it's more complete
                        logger.info(f"Array field '{field}': Using larger array ({new_len} vs {existing_len} items)")
                        merged[field] = new_value
                    elif existing_len > new_len * 1.5:  # Existing is significantly larger
                        logger.info(f"Array field '{field}': Keeping existing {existing_len} items (more complete than {new_len})")
                        # Keep existing
                    else:
                        # Similar lengths - concatenate and deduplicate
                        if all(isinstance(item, (str, int, float, bool)) for item in merged[field] + new_value):
                            # Simple types - deduplicate
                            merged[field] = list(dict.fromkeys(merged[field] + new_value))
                        else:
                            # Complex types (objects) - just concatenate
                            merged[field] = merged[field] + new_value
                        logger.info(f"Merged array field '{field}': Concatenated to {len(merged[field])} total items")
                elif isinstance(new_value, list):
                    # Existing was not an array but should be, replace
                    logger.info(f"Array field '{field}': Setting initial value with {len(new_value)} items")
                    merged[field] = new_value
            else:
                # Scalar field - choose most valid value
                if merged[field] != new_value:
                    existing_val = str(merged[field]) if merged[field] else ""
                    new_val = str(new_value) if new_value else ""

                    # For email fields, ONLY accept values with @ symbol
                    if 'email' in field.lower():
                        has_existing_at = '@' in existing_val
                        has_new_at = '@' in new_val

                        if has_new_at and not has_existing_at:
                            # New value is valid email, existing is not
                            logger.info(f"Field '{field}': replacing '{existing_val}' with valid email '{new_val}'")
                            merged[field] = new_value
                        elif has_existing_at and not has_new_at:
                            # Keep existing valid email, reject invalid new value
                            logger.info(f"Field '{field}': keeping valid email '{existing_val}', rejecting '{new_val}'")
                        elif has_new_at and has_existing_at:
                            # Both are emails, keep first one
                            logger.info(f"Field '{field}': keeping first email '{existing_val}'")
                        else:
                            # Neither is valid email, keep existing
                            logger.warning(f"Field '{field}': no valid email found ('{existing_val}' vs '{new_val}'), keeping first")
                    else:
                        # For non-email fields, prefer longer/more detailed values
                        if len(new_val) > len(existing_val):
                            logger.info(f"Field '{field}': using more detailed value '{new_val}' over '{existing_val}'")
                            merged[field] = new_value
                        else:
                            logger.debug(f"Field '{field}': keeping '{existing_val}'")

        return merged

    def _extract_from_text_only(self, text: str, schema: Dict[str, str]) -> Dict[str, Any]:
        """Extract using text-only vision model (fallback) with section-aware parsing"""
        try:
            schema_description = self._format_schema_for_prompt(schema)

            prompt = f"""Extract data from this document text as JSON.

FIELDS TO EXTRACT:
{schema_description}

CRITICAL RULES:
1. Section Header Matching (HIGHEST PRIORITY):
   - ONLY extract from sections with matching numbered headers
   - Look for numbered section headers like "1.", "2.", "4.", "8." followed by section names
   - "warranty" field → ONLY from "8. WARRANTY" or "WARRANTY" section header
   - "deliverables" field → ONLY from "4. DELIVERABLES" or "DELIVERABLES" section header
   - "scope_of_service" field → ONLY from "1. SCOPE OF SERVICES" or "SCOPE OF SERVICE" section header
   - DO NOT extract a field from a bullet point list UNLESS that list is under the matching section header
   - If you see warranty-related text in a deliverables bullet list, it is NOT warranty - ignore it

2. Field vs Section Distinction:
   - If "warranty" appears in a numbered list under "4. DELIVERABLES", ignore it (it's a deliverable item)
   - If "warranty" has its own section header "8. WARRANTY", extract from there
   - Section headers are usually numbered (1., 2., 8.) and may be in CAPS or bold

3. Output Format:
   - Return ONLY valid JSON with exact field names above
   - No markdown, no code fences, no commentary
   - Use null for missing fields or if section not found in text

4. Array Fields:
   - Extract ALL bullet points from the matched section ONLY
   - If "scope_of_service" is array, extract bullets ONLY from "1. SCOPE OF SERVICES" section
   - If "deliverables" is array, extract bullets ONLY from "4. DELIVERABLES" section
   - Keep complete sentences together as single array items

5. Text Structure:
   - Sections are separated by numbered headers (1., 2., etc.)
   - Content under a section belongs to that section until next numbered header
   - Bullet points (•, -, numbered lists) belong to their parent section

Example - WRONG extraction:
Text shows:
"4. DELIVERABLES
- Complete source code
- 60 days warranty support"

{{"warranty": "60 days"}} ← WRONG! This is from deliverables section, not warranty section!

Example - CORRECT extraction:
Text shows:
"4. DELIVERABLES
- Complete source code
- Technical documentation"
"8. WARRANTY
Contractor warrants work will be free from defects for 90 days"

{{"deliverables": ["Complete source code", "Technical documentation"], "warranty": "90 days"}} ← CORRECT!

Document text:
{text[:4000]}

Return ONLY valid JSON with the exact field names specified."""

            response = self.client.chat.completions.create(
                model=config.VISION_MODEL,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=config.VISION_MAX_TOKENS,
                temperature=config.VISION_TEMPERATURE,
                timeout=180.0  # 3 minutes for slower inference servers
            )

            result_text = response.choices[0].message.content
            extracted_data = self._parse_json_response(result_text)

            return extracted_data if extracted_data else self._mock_extraction(schema)

        except Exception as e:
            logger.error(f"Text-only extraction error: {str(e)}")
            return self._mock_extraction(schema)

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON from model response with smart extraction and sanitization"""
        import json
        import re

        def extract_json_object(text: str) -> str:
            """Extract JSON object by finding matching braces (first { to last })"""
            first_brace = text.find('{')
            if first_brace == -1:
                return ""

            # Find matching closing brace by counting
            brace_count = 0
            last_brace = -1

            for i in range(first_brace, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_brace = i
                        break

            if last_brace == -1:
                # No matching brace found, find last } in text
                last_brace = text.rfind('}')
                if last_brace == -1:
                    return text[first_brace:]  # Return from first { to end

            return text[first_brace:last_brace + 1]

        def sanitize_json_strings(json_str: str) -> str:
            """Sanitize control characters and fix corrupted string values"""
            # Remove NULL bytes
            sanitized = json_str.replace('\x00', '')

            # Fix pattern: "field": "value that may span
            # multiple lines or have garbage"
            # We need to handle cases where value contains unescaped newlines or quotes

            def fix_field_value(match):
                field_name = match.group(1)
                # Everything after the colon and opening quote until we hit valid JSON again
                rest = match.group(2)

                # Find where the value should end (next field or closing brace)
                # Look for patterns like: ",\n  "field": or }\n
                next_field = re.search(r'[,\}]\s*(?:\n\s*)?"', rest)
                if next_field:
                    value = rest[:next_field.start()]
                else:
                    value = rest

                # Clean the value: remove literal newlines, escape special chars, remove garbage
                value = re.sub(r'\s*\n\s*', ' ', value)  # Replace newlines with space
                value = re.sub(r'\s+', ' ', value).strip()  # Normalize whitespace
                # Remove random garbage words that shouldn't be there
                value = re.sub(r'\s*addCriterion\s*', '', value)
                # Escape any remaining control characters
                value = value.replace('\r', ' ').replace('\t', ' ')

                return f'"{field_name}": "{value}"'

            # Match "field": " and capture everything after
            sanitized = re.sub(r'"([^"]+)":\s*"([^}]+?)(?="[^"]*":|$)', fix_field_value, sanitized, flags=re.DOTALL)

            return sanitized

        def fix_truncated_json(json_str: str) -> str:
            """Attempt to fix truncated JSON by closing structures"""
            fixed = json_str.strip()

            # Remove trailing comma
            if fixed.endswith(','):
                fixed = fixed[:-1]

            # If string count is odd, we have an unclosed string
            if fixed.count('"') % 2 != 0:
                # Find the last complete field and truncate there
                last_comma = fixed.rfind('",')
                if last_comma != -1:
                    fixed = fixed[:last_comma + 1]
                else:
                    # Find last colon and set to null
                    last_colon = fixed.rfind('":')
                    if last_colon != -1:
                        fixed = fixed[:last_colon + 1] + ' null'

            # Close any unclosed brackets and braces
            open_brackets = fixed.count('[') - fixed.count(']')
            open_braces = fixed.count('{') - fixed.count('}')

            fixed += ']' * open_brackets
            fixed += '}' * open_braces

            return fixed

        # Step 1: Try direct parse (best case)
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # Step 2: Extract JSON object (from first { to matching })
        json_str = extract_json_object(response_text)

        if not json_str:
            logger.error(f"Could not find JSON object in response: {response_text[:200]}")
            return {}

        # Step 3: Try parsing extracted JSON
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug(f"Extracted JSON parse failed: {str(e)}, attempting repair...")

        # Step 4: Sanitize control characters in string values
        try:
            sanitized = sanitize_json_strings(json_str)
            return json.loads(sanitized)
        except json.JSONDecodeError as e:
            logger.debug(f"Sanitized JSON parse failed: {str(e)}, attempting truncation fix...")

        # Step 5: Try fixing truncation
        try:
            fixed = fix_truncated_json(json_str)
            result = json.loads(fixed)
            logger.warning("Successfully repaired truncated/malformed JSON - some data may be incomplete")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"All JSON repair attempts failed: {str(e)}")
            logger.error(f"Failed JSON preview: {json_str[:300]}")
            return {}

    def _format_schema_for_prompt(self, schema: Dict[str, str]) -> str:
        """Format schema for prompt with helpful descriptions"""
        lines = []

        # Field-specific extraction hints to improve accuracy
        field_hints = {
            # Section-based array fields
            "deliverables": "array from section '4. DELIVERABLES'",
            "deliverable": "array from 'DELIVERABLES' section",
            "scope_of_work": "array from section '1. SCOPE OF WORK' or '1. SCOPE OF SERVICES'",
            "scope_of_services": "array from section '1. SCOPE OF SERVICES'",
            "scope_of_service": "array from section '1. SCOPE OF SERVICES'",

            # Representative fields
            "contractor_representative": "text following 'Representative:' label in AND/contractor section",
            "contractor_representative_name": "text following 'Representative:' label in contractor section",
            "client_representative": "text following 'Representative:' label in BETWEEN/client section",
            "client_representative_name": "text following 'Representative:' label in client section",

            # Email fields
            "contractor_email": "email address following 'Email:' label in AND/contractor section",
            "client_email": "email address following 'Email:' label in BETWEEN/client section",

            # Company fields
            "contractor_name": "text following 'Company Name:' in contractor section",
            "client_company_name": "text following 'Company Name:' in client section",

            # Medical/invoice common fields
            "medications": "array of prescribed medicines",
            "line_items": "array of items with details"
        }

        for field, field_type in schema.items():
            # Check if field_type is a dict (nested schema) or string
            if isinstance(field_type, dict):
                type_str = field_type.get("type", "string")
                description = field_type.get("description", "")
            else:
                type_str = field_type
                description = ""

            # Use custom hint if available, otherwise use description from schema
            hint = field_hints.get(field.lower(), description)

            if hint:
                lines.append(f"- {field} ({type_str}): {hint}")
            else:
                lines.append(f"- {field} ({type_str})")

        return "\n".join(lines)

    def _classify_by_keywords(self, text: str) -> Dict[str, Any]:
        """
        Fast rule-based classification using keyword patterns.
        Returns classification result or None if no confident match.
        """
        text_lower = text.lower()

        # Prescription indicators (high confidence)
        prescription_keywords = ['prescription', 'rx ', 'medication', 'dosage', 'sig:', 'pharmacy', 'prescriber', 'refills']
        prescription_count = sum(1 for kw in prescription_keywords if kw in text_lower)
        if prescription_count >= 2:
            return {
                "document_type": "prescription",
                "confidence": 0.85,
                "reasoning": f"Contains {prescription_count} prescription-specific keywords"
            }

        # Invoice indicators
        invoice_keywords = ['invoice', 'invoice number', 'invoice #', 'bill to', 'payment terms', 'net ', 'due date']
        invoice_count = sum(1 for kw in invoice_keywords if kw in text_lower)
        if invoice_count >= 2:
            return {
                "document_type": "invoice",
                "confidence": 0.85,
                "reasoning": f"Contains {invoice_count} invoice-specific keywords"
            }

        # Contract indicators
        contract_keywords = ['agreement', 'hereby', 'whereas', 'party', 'contract', 'terms and conditions', 'signed']
        contract_count = sum(1 for kw in contract_keywords if kw in text_lower)
        if contract_count >= 3:
            return {
                "document_type": "contract",
                "confidence": 0.85,
                "reasoning": f"Contains {contract_count} contract-specific keywords"
            }

        # Bank statement indicators
        bank_keywords = ['account number', 'statement period', 'beginning balance', 'ending balance', 'transaction']
        bank_count = sum(1 for kw in bank_keywords if kw in text_lower)
        if bank_count >= 2:
            return {
                "document_type": "bank_statement",
                "confidence": 0.85,
                "reasoning": f"Contains {bank_count} banking-specific keywords"
            }

        # Receipt indicators
        receipt_keywords = ['receipt', 'thank you', 'payment method', 'subtotal', 'tax', 'change due']
        receipt_count = sum(1 for kw in receipt_keywords if kw in text_lower)
        if receipt_count >= 2:
            return {
                "document_type": "receipt",
                "confidence": 0.80,
                "reasoning": f"Contains {receipt_count} receipt-specific keywords"
            }

        return None

    def _build_types_description(self, available_types: List[str]) -> str:
        """
        Build a formatted description of available document types with common indicators.

        Args:
            available_types: List of document types available in the database

        Returns:
            Formatted string describing each type
        """
        type_indicators = {
            "invoice": "vendor name, invoice number, line items with prices, total amount, payment terms",
            "prescription": "patient info, doctor/prescriber name, medication names, dosage instructions, pharmacy",
            "bank_statement": "account number, statement period dates, transaction list, balances",
            "receipt": "store/business name, items purchased, subtotal, tax, total, payment method",
            "contract": "legal language (\"hereby\", \"whereas\"), party names, signatures, terms/conditions, sections",
            "service_contract": "service agreement, deliverables, scope of work, payment terms, signatures",
            "report": "title, sections, analysis, data tables, conclusions, recommendations"
        }

        descriptions = []
        for doc_type in available_types:
            # Normalize type for matching (remove underscores, lowercase)
            normalized_type = doc_type.lower().replace("_", " ").replace("-", " ")
            type_key = doc_type.lower().replace("_", "").replace("-", "")

            # Try to find matching indicators
            indicators = None
            for key, value in type_indicators.items():
                if key.replace("_", "").replace("-", "") == type_key:
                    indicators = value
                    break

            if indicators:
                descriptions.append(f"• {doc_type} - Typical indicators: {indicators}")
            else:
                # Generic description for unknown types
                descriptions.append(f"• {doc_type} - Custom document type")

        return "\n".join(descriptions)

    def detect_document_type(self, pdf_content: bytes, available_types: List[str] = None) -> Dict[str, Any]:
        """
        Detect the type of document using hybrid approach against available template types.
        1. Fast keyword-based classification (50ms)
        2. VL model fallback for unclear cases (5-10 seconds)

        Args:
            pdf_content: Binary PDF content
            available_types: List of document types that have templates in the database

        Returns dict with:
        - document_type: str (e.g., "invoice", "prescription", "bank_statement")
        - confidence: float (0.0-1.0)
        - reasoning: str (explanation)
        """
        if not self.client:
            logger.warning("No vision client. Returning mock document type.")
            return {"document_type": "unknown", "confidence": 0.0, "reasoning": "Vision service unavailable"}

        if not available_types:
            logger.warning("No available document types provided for classification")
            return {"document_type": "unknown", "confidence": 0.0, "reasoning": "No templates available in the system"}

        try:
            # STEP 1: Extract first page text for fast classification
            text = self._extract_text_from_pages(pdf_content, page_numbers=[1])

            # STEP 2: Try fast keyword-based classification first
            if len(text.strip()) >= 50:
                keyword_result = self._classify_by_keywords(text)
                if keyword_result and keyword_result['confidence'] >= 0.80:
                    logger.info(f"Fast classification: {keyword_result['document_type']} ({keyword_result['confidence']:.0%})")
                    return keyword_result

            # STEP 3: If no text or low confidence, use VL model with optimized image
            if len(text.strip()) < 50:
                logger.info("Limited text found, using image for document type detection")
                page_images = self._pdf_to_images(pdf_content, page_numbers=[1], zoom=1.0)  # Reduced zoom
                if not page_images:
                    raise ValueError("Cannot extract text or images from PDF")

                # Optimize image size before sending
                img = page_images[0]
                max_width = 800  # Reduced from potentially 2000+
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_size = (max_width, int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    logger.info(f"Resized image to {new_size[0]}x{new_size[1]} for faster processing")

                # Compress as JPEG for smaller size
                buffered = BytesIO()
                img.convert('RGB').save(buffered, format="JPEG", quality=85, optimize=True)
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
                img_size_kb = len(buffered.getvalue()) / 1024
                logger.info(f"Optimized image size: {img_size_kb:.1f}KB")

                # Build dynamic prompt with available types
                types_description = self._build_types_description(available_types)

                message_content = [
                    {"type": "text", "text": f"""Analyze this document image and classify its type.

AVAILABLE DOCUMENT TYPES IN SYSTEM (choose ONE from this list ONLY):
{types_description}

IMPORTANT:
- You MUST choose ONE type from the list above
- If the document doesn't clearly match any type, choose the closest match with lower confidence
- DO NOT suggest types that are not in the list above

RESPONSE FORMAT (JSON only):
{{
  "document_type": "<one type from list above>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<2-3 key visual indicators you see>"
}}

Look at the document carefully and identify the strongest visual indicators."""},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_base64}",
                            "detail": "low"
                        }
                    }
                ]
            else:
                # Text-based classification with dynamic types
                types_description = self._build_types_description(available_types)

                message_content = f"""Analyze this document text and classify its type.

Document text excerpt:
{text[:800]}

AVAILABLE DOCUMENT TYPES IN SYSTEM (choose ONE from this list ONLY):
{types_description}

IMPORTANT:
- You MUST choose ONE type from the list above
- If the document doesn't clearly match any type, choose the closest match with lower confidence
- DO NOT suggest types that are not in the list above

RESPONSE FORMAT (JSON only):
{{
  "document_type": "<one type from list above>",
  "confidence": <0.0 to 1.0>,
  "reasoning": "<2-3 key text patterns you found>"
}}

Return ONLY valid JSON, no other text."""

            # Call VL model with extended timeout for slower inference servers
            response = self.client.chat.completions.create(
                model=config.DETECTION_MODEL,
                messages=[{"role": "user", "content": message_content}],
                max_tokens=300,  # Increased for better reasoning
                temperature=0.2,  # Slightly higher for flexibility
                timeout=120.0  # 2 minutes for classification on slower servers
            )

            result = self._parse_json_response(response.choices[0].message.content)

            if not result or not result.get('document_type'):
                logger.warning("VL model returned empty result")
                return {"document_type": "undetected", "confidence": 0.0, "reasoning": "Could not determine document type"}

            logger.info(f"VL classification: {result.get('document_type')} ({result.get('confidence', 0):.0%})")
            return result

        except TimeoutError:
            logger.error("Document classification timed out after 2 minutes")
            return {
                "document_type": "undetected",
                "confidence": 0.0,
                "reasoning": "Classification timed out. Please select a template manually."
            }
        except Exception as e:
            logger.error(f"Document type detection failed: {str(e)}")
            return {
                "document_type": "undetected",
                "confidence": 0.0,
                "reasoning": f"Classification failed: {str(e)}"
            }

    def _mock_extraction(self, schema: Dict[str, str]) -> Dict[str, Any]:
        """Generate mock data based on schema"""
        mock_data = {}
        for field, field_type in schema.items():
            if "invoice" in field.lower() or "number" in field.lower():
                mock_data[field] = "INV-2024-001"
            elif "date" in field.lower():
                mock_data[field] = "2024-12-29"
            elif "vendor" in field.lower() or "company" in field.lower():
                mock_data[field] = "Acme Corporation"
            elif "total" in field.lower() or "amount" in field.lower():
                mock_data[field] = 1250.00
            elif field_type == "array":
                mock_data[field] = [
                    {"description": "Consulting Services", "amount": 1000.00},
                    {"description": "Software License", "amount": 250.00}
                ]
            else:
                mock_data[field] = f"Mock {field}"

        return mock_data

    def process_chat_message(self, message: str, current_schema: Dict[str, str]) -> tuple[str, Dict[str, str]]:
        """Process chat message to build extraction schema"""

        if not self.client:
            return self._mock_chat_response(message, current_schema)

        try:
            schema_str = "\n".join([f"- {k}: {v}" for k, v in current_schema.items()]) if current_schema else "None yet"

            system_prompt = """You are a helpful assistant that helps users build document extraction schemas.

When users greet you or ask questions: Respond conversationally and ask what fields they want to extract.
When users request fields: Update the schema and confirm.

FIELD NAME RULES:
- Use snake_case
- Use EXACT names user specifies
- Plural words (deliverables, medications, items) = array type
- NO typos, NO extra letters, NO suffix additions like "_list"

DATA TYPES:
- string: text, names, emails
- number: integers, floats
- date: dates
- array: lists, multiple items, plural nouns
- object: nested structures

USER REQUEST PATTERNS:
"extract X" or "add X" → ADD field X to schema (determine type from name)
"extract X as array" → ADD field X with type=array
"remove X" → DELETE field X from schema
"replace X with Y" → DELETE X, ADD Y
"X and Y as well" → ADD both X and Y to schema
"X, Y, Z" → ADD all three to schema
"hi", "hello", "help" → Greet and ask what to extract

RESPONSE FORMAT (JSON only):
{
  "reply": "Your conversational response",
  "schema": {"field1": "type1", "field2": "type2"}
}

EXAMPLES:
User: "hi"
Response: {"reply": "Hello! I'll help you configure document extraction. What fields would you like to extract from your documents?", "schema": {}}

User: "extract deliverables"
Response: {"reply": "Added deliverables as an array field. What else would you like to extract?", "schema": {"deliverables": "array"}}

User: "add client_email and contractor_email"
Response: {"reply": "Added client_email and contractor_email fields.", "schema": {"deliverables": "array", "client_email": "string", "contractor_email": "string"}}"""

            user_prompt = f"""Current schema:
{schema_str}

User request: {message}

Process this request and update the schema accordingly."""

            response = self.client.chat.completions.create(
                model=config.VISION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=800,
                temperature=0.3,
                timeout=120.0  # 2 minutes for chat processing on slower servers
            )

            result = self._parse_json_response(response.choices[0].message.content)

            reply = result.get("reply", "I'm here to help! What would you like to extract?")
            updated_schema = result.get("schema", current_schema)

            logger.info(f"Chat processed: {len(updated_schema)} fields in schema")

            return reply, updated_schema

        except Exception as e:
            logger.error(f"Chat processing error: {str(e)}")
            return self._mock_chat_response(message, current_schema)

    def _mock_chat_response(self, message: str, current_schema: Dict[str, str]) -> tuple[str, Dict[str, str]]:
        """Mock chat response when vision client is not available"""
        message_lower = message.lower()

        if not current_schema:
            if "invoice" in message_lower:
                reply = "I'll help you extract invoice data. What fields do you need? Common invoice fields include: invoice number, date, vendor, line items, and total amount."
                return reply, {}
            else:
                reply = "I can help you define what data to extract from your documents. What type of document are you working with?"
                return reply, {}

        new_schema = dict(current_schema)

        if "invoice number" in message_lower or "number" in message_lower:
            new_schema["invoice_number"] = "string"
        if "date" in message_lower:
            new_schema["date"] = "date"
        if "vendor" in message_lower or "company" in message_lower:
            new_schema["vendor"] = "string"
        if "total" in message_lower or "amount" in message_lower:
            new_schema["total"] = "number"
        if "line item" in message_lower or "items" in message_lower:
            new_schema["line_items"] = "array"

        if new_schema != current_schema:
            field_list = ", ".join(new_schema.keys())
            reply = f"Got it! I'll extract these fields: {field_list}. You can test this extraction or add more fields."
        else:
            reply = "What other fields would you like to extract?"

        return reply, new_schema

    def _extract_schema_from_response(self, message: str, current_schema: Dict[str, str]) -> Dict[str, str]:
        """Extract schema updates from user message"""
        new_schema = dict(current_schema)
        message_lower = message.lower()

        field_mappings = {
            "invoice number": ("invoice_number", "string"),
            "invoice_number": ("invoice_number", "string"),
            "date": ("date", "date"),
            "vendor": ("vendor", "string"),
            "company": ("vendor", "string"),
            "total": ("total", "number"),
            "amount": ("total", "number"),
            "line items": ("line_items", "array"),
            "items": ("line_items", "array"),
        }

        for keyword, (field, field_type) in field_mappings.items():
            if keyword in message_lower:
                new_schema[field] = field_type

        return new_schema
