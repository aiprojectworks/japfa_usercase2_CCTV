import csv
from datetime import datetime
from dataclasses import dataclass
from typing import List

@dataclass
class ViolationRecord:
    timestamp: datetime
    factory_area: str
    inspection_section: str
    violation_type: str
    image_url: str
    resolved: bool = False
    confirmed: bool = False
    row_index: int = -1

    @classmethod
    def from_csv_row(cls, row: List[str], row_index: int = -1) -> 'ViolationRecord':
        # Clean and validate row data
        timestamp_str = row[0].strip()
        factory_area = row[1].strip() if len(row) > 1 else ""
        inspection_section = row[2].strip() if len(row) > 2 else ""
        violation_type = row[3].strip() if len(row) > 3 else ""
        image_url = row[4].strip() if len(row) > 4 else ""
        resolved = row[5].lower().strip() == 'true' if len(row) > 5 and row[5].strip() else False
        confirmed = row[6].lower().strip() == 'true' if len(row) > 6 and row[6].strip() else False
        
        timestamp = datetime.strptime(timestamp_str, "%m/%d/%y %I:%M %p")
        
        return cls(
            timestamp=timestamp,
            factory_area=factory_area,
            inspection_section=inspection_section,
            violation_type=violation_type,
            image_url=image_url,
            resolved=resolved,
            confirmed=confirmed,
            row_index=row_index
        )

class DataParser:
    def __init__(self, file_path: str = None):
        import os
        if file_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(script_dir, "data", "data.csv")
        self.file_path = file_path
        self.records: List[ViolationRecord] = []

    def parse(self) -> List[ViolationRecord]:
        self.records = []  # Clear existing records
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as file:
                csv_reader = csv.reader(file)
                header = next(csv_reader, None)  # Skip header row, handle empty file
                
                if header is None:
                    return self.records

                for row_index, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
                    # Skip empty rows or rows with insufficient data
                    if len(row) < 5 or not row[0].strip():
                        continue
                    
                    try:
                        # Validate timestamp format before creating record
                        datetime.strptime(row[0].strip(), "%m/%d/%y %I:%M %p")
                        record = ViolationRecord.from_csv_row(row, row_index)
                        self.records.append(record)
                    except ValueError as e:
                        # Log malformed timestamp but continue processing
                        print(f"Warning: Skipping row {row_index} due to invalid timestamp '{row[0]}': {e}")
                        continue
                    except Exception as e:
                        # Log other parsing errors but continue
                        print(f"Warning: Skipping row {row_index} due to parsing error: {e}")
                        continue

        except FileNotFoundError:
            print(f"Warning: CSV file not found at {self.file_path}")
        except Exception as e:
            print(f"Error reading CSV file: {e}")

        return self.records

    def get_records_by_violation_type(self, violation_type: str) -> List[ViolationRecord]:
        return [record for record in self.records if record.violation_type == violation_type]

    def get_records_by_factory_area(self, factory_area: str) -> List[ViolationRecord]:
        return [record for record in self.records if record.factory_area == factory_area]

    def update_resolved_status(self, row_index: int, resolved: bool = True) -> bool:
        """Update the resolved status of a record in the CSV file"""
        import tempfile
        import shutil
        
        try:
            # Read all lines
            with open(self.file_path, 'r', encoding='utf-8') as file:
                lines = list(csv.reader(file))
            
            # Update the specific row
            if 0 < row_index <= len(lines):
                if len(lines[row_index - 1]) >= 6:
                    lines[row_index - 1][5] = str(resolved).lower()
                else:
                    lines[row_index - 1].append(str(resolved).lower())
                
                # Ensure confirmed column exists
                if len(lines[row_index - 1]) < 7:
                    lines[row_index - 1].append('false')
                
                # Write back to file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', newline='') as temp_file:
                    writer = csv.writer(temp_file)
                    writer.writerows(lines)
                    temp_file_path = temp_file.name
                
                shutil.move(temp_file_path, self.file_path)
                
                # Update the record in memory
                for record in self.records:
                    if record.row_index == row_index:
                        record.resolved = resolved
                        break
                
                return True
        except Exception as e:
            print(f"Error updating CSV: {e}")
            return False
        
        return False

    def get_unresolved_records(self) -> List[ViolationRecord]:
        """Get all unresolved violation records"""
        return [record for record in self.records if not record.resolved]

    def get_unconfirmed_records(self) -> List[ViolationRecord]:
        """Get all unconfirmed violation records"""
        return [record for record in self.records if not record.confirmed]

    def update_confirmed_status(self, row_index: int, confirmed: bool = True) -> bool:
        """Update the confirmed status of a record in the CSV file"""
        import tempfile
        import shutil
        
        try:
            # Read all lines
            with open(self.file_path, 'r', encoding='utf-8') as file:
                lines = list(csv.reader(file))
            
            # Update the specific row
            if 0 < row_index <= len(lines):
                # Ensure we have enough columns
                while len(lines[row_index - 1]) < 7:
                    lines[row_index - 1].append('false')
                
                lines[row_index - 1][6] = str(confirmed).lower()
                
                # Write back to file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', newline='') as temp_file:
                    writer = csv.writer(temp_file)
                    writer.writerows(lines)
                    temp_file_path = temp_file.name
                
                shutil.move(temp_file_path, self.file_path)
                
                # Update the record in memory
                for record in self.records:
                    if record.row_index == row_index:
                        record.confirmed = confirmed
                        break
                
                return True
        except Exception as e:
            print(f"Error updating CSV: {e}")
            return False
        
        return False

    def add_example_violation(self) -> ViolationRecord:
        """Add an example violation to the CSV file for testing"""
        from datetime import datetime
        import random
        
        # Example violation data
        example_violations = [
            {
                "area": "KP1, Production Line A",
                "section": "Assembly Station 3",
                "violation": "员工未佩戴安全帽",
                "image": "https://example.com/safety_helmet_violation.jpg"
            },
            {
                "area": "KP2, Warehouse B", 
                "section": "Loading Dock",
                "violation": "叉车违规操作",
                "image": "https://example.com/forklift_violation.jpg"
            },
            {
                "area": "KP3, Quality Control",
                "section": "Inspection Area",
                "violation": "工作区域未清洁",
                "image": "https://example.com/cleanliness_violation.jpg"
            }
        ]
        
        # Select random example
        violation_data = random.choice(example_violations)
        
        # Create timestamp
        now = datetime.now()
        timestamp_str = now.strftime("%m/%d/%y %I:%M %p")
        
        # Prepare CSV row
        new_row = [
            timestamp_str,
            violation_data["area"],
            violation_data["section"],
            violation_data["violation"],
            violation_data["image"],
            "false",
            "false"  # confirmed column
        ]
        
        try:
            # Append to CSV file
            with open(self.file_path, 'a', encoding='utf-8', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(new_row)
            
            # Create ViolationRecord object
            record = ViolationRecord(
                timestamp=now,
                factory_area=violation_data["area"],
                inspection_section=violation_data["section"],
                violation_type=violation_data["violation"],
                image_url=violation_data["image"],
                resolved=False,
                confirmed=False,
                row_index=-1  # Will be set when re-parsed
            )
            
            return record
            
        except Exception as e:
            print(f"Error adding example violation: {e}")
            return None

# Usage example:
# parser = DataParser()
# records = parser.parse()
# for record in records:
#     print(f"Time: {record.timestamp}, Area: {record.factory_area}, Violation: {record.violation_type}")
