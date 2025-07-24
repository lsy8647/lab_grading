# grader.py - 자동 채점 시스템 (한 번만 설정하면 끝!)
# 이 파일은 Git 저장소에 저장되어 학생용 노트북에서 자동으로 로드됩니다.

import requests
import json
import pandas as pd
from typing import Any, Dict, List
import numpy as np

class AutoGrader:
    def __init__(self, repo_url: str, branch: str = "main"):
        """자동 채점 시스템 초기화"""
        self.repo_url = repo_url.rstrip('/')
        self.branch = branch
        
    def fetch_answer_file(self, file_path: str) -> Dict[str, Any]:
        """Git 저장소에서 정답 파일을 가져옴"""
        try:
            url = f"{self.repo_url}/{file_path}"
            response = requests.get(url)
            response.raise_for_status()
            return json.loads(response.text)
        except Exception as e:
            print(f"❌ 정답 파일을 가져오는데 실패했습니다: {e}")
            return {}
    
    def check_answer(self, problem_id: str, student_answer: Any, answer_file: str = "answers.json") -> Dict[str, Any]:
        """학생 답안을 채점"""
        answers = self.fetch_answer_file(answer_file)
        
        if problem_id not in answers:
            return {"status": "error", "message": f"문제 {problem_id}를 찾을 수 없습니다."}
        
        correct_answer = answers[problem_id]
        result = self._compare_answers(student_answer, correct_answer)
        
        return {
            "problem_id": problem_id,
            "correct": result["match"],
            "feedback": result["feedback"],
            "expected": correct_answer.get("display_answer", "정답 비공개"),
            "student_answer": student_answer
        }
    
    def _compare_answers(self, student_answer: Any, correct_answer: Dict[str, Any]) -> Dict[str, Any]:
        """답안 비교 로직"""
        answer_type = correct_answer.get("type", "exact")
        expected = correct_answer["answer"]
        tolerance = correct_answer.get("tolerance", 0)
        
        try:
            if answer_type == "exact":
                match = student_answer == expected
                feedback = "정답입니다! 🎉" if match else "틀렸습니다. 다시 시도해보세요."
                
            elif answer_type == "numeric":
                if isinstance(student_answer, (int, float)) and isinstance(expected, (int, float)):
                    diff = abs(student_answer - expected)
                    match = diff <= tolerance
                    feedback = "정답입니다! 🎉" if match else f"근사값이 맞지 않습니다. (오차: {diff:.4f})"
                else:
                    match = False
                    feedback = "숫자 형태의 답안이 필요합니다."
                    
            elif answer_type == "list":
                if isinstance(student_answer, list) and isinstance(expected, list):
                    match = sorted(student_answer) == sorted(expected)
                    feedback = "정답입니다! 🎉" if match else "리스트 내용이 일치하지 않습니다."
                else:
                    match = False
                    feedback = "리스트 형태의 답안이 필요합니다."
                    
            elif answer_type == "dataframe":
                if isinstance(student_answer, pd.DataFrame) and isinstance(expected, dict):
                    student_dict = student_answer.to_dict()
                    match = student_dict == expected
                    feedback = "정답입니다! 🎉" if match else "DataFrame이 일치하지 않습니다."
                else:
                    match = False
                    feedback = "DataFrame 형태의 답안이 필요합니다."
                    
            elif answer_type == "series_dtype":
                # Series의 값과 dtype을 모두 체크
                if hasattr(student_answer, 'dtype') and hasattr(student_answer, 'values'):
                    expected_values = expected["values"]
                    expected_dtype = expected["dtype"]
                    
                    values_match = list(student_answer.values) == expected_values
                    dtype_match = str(student_answer.dtype) == expected_dtype
                    
                    match = values_match and dtype_match
                    if match:
                        feedback = "정답입니다! 🎉"
                    elif not values_match:
                        feedback = "Series의 값이 일치하지 않습니다."
                    else:
                        feedback = f"dtype이 일치하지 않습니다. 현재: {student_answer.dtype}, 기대값: {expected_dtype}"
                else:
                    match = False
                    feedback = "Series 형태의 답안이 필요합니다."
                    
            elif answer_type == "series_values":
                # Series의 값만 체크 (dtype 무관)
                if hasattr(student_answer, 'values'):
                    match = list(student_answer.values) == expected
                    feedback = "정답입니다! 🎉" if match else "Series의 값이 일치하지 않습니다."
                else:
                    match = False
                    feedback = "Series 형태의 답안이 필요합니다."
                    
            elif answer_type == "function":
                test_cases = correct_answer.get("test_cases", [])
                passed = 0
                total = len(test_cases)
                
                for test_case in test_cases:
                    try:
                        input_args = test_case["input"]
                        expected_output = test_case["output"]
                        
                        if isinstance(input_args, list):
                            actual_output = student_answer(*input_args)
                        else:
                            actual_output = student_answer(input_args)
                            
                        if actual_output == expected_output:
                            passed += 1
                    except Exception as e:
                        continue
                
                match = passed == total
                if match:
                    feedback = f"모든 테스트 케이스 통과! 🎉"
                else:
                    feedback = f"테스트 케이스 {passed}/{total} 통과 - 다시 확인해보세요!"
                    
            elif answer_type == "code_pattern":
                # 코드 패턴을 문자열로 체크 (matplotlib 등)
                if isinstance(student_answer, str):
                    required_patterns = expected.get("required", [])
                    forbidden_patterns = expected.get("forbidden", [])
                    
                    # 필수 패턴 체크
                    missing_patterns = []
                    for pattern in required_patterns:
                        if pattern not in student_answer:
                            missing_patterns.append(pattern)
                    
                    # 금지 패턴 체크  
                    found_forbidden = []
                    for pattern in forbidden_patterns:
                        if pattern in student_answer:
                            found_forbidden.append(pattern)
                    
                    if not missing_patterns and not found_forbidden:
                        match = True
                        feedback = "코드 패턴이 올바릅니다! 🎉"
                    else:
                        match = False
                        feedback_parts = []
                        if missing_patterns:
                            feedback_parts.append(f"누락된 패턴: {', '.join(missing_patterns)}")
                        if found_forbidden:
                            feedback_parts.append(f"사용하면 안 되는 패턴: {', '.join(found_forbidden)}")
                        feedback = " | ".join(feedback_parts)
                else:
                    match = False
                    feedback = "코드를 문자열로 제출해주세요."
                    
            elif answer_type == "array_shape":
                # numpy 배열의 형태 체크
                if hasattr(student_answer, 'shape'):
                    expected_shape = tuple(expected)
                    match = student_answer.shape == expected_shape
                    feedback = "정답입니다! 🎉" if match else f"배열 형태가 틀렸습니다. 현재: {student_answer.shape}, 기대값: {expected_shape}"
                else:
                    match = False
                    feedback = "numpy 배열이 필요합니다."
                    
            elif answer_type == "array_values":
                # numpy 배열의 값 체크
                if hasattr(student_answer, 'tolist'):
                    student_list = student_answer.tolist()
                    match = student_list == expected
                    feedback = "정답입니다! 🎉" if match else "배열의 값이 일치하지 않습니다."
                else:
                    match = False
                    feedback = "numpy 배열이 필요합니다."
                
            else:
                match = False
                feedback = "지원하지 않는 답안 타입입니다."
                
        except Exception as e:
            match = False
            feedback = f"채점 중 오류가 발생했습니다: {str(e)}"
        
        return {"match": match, "feedback": feedback}

# 전역 채점 시스템 인스턴스 생성
# ⚠️ 여기를 본인의 GitHub 저장소 URL로 수정하세요! (한 번만!)
REPO_URL = "https://raw.githubusercontent.com/lsy8647/lab_grading/refs/heads/main/"
grader = AutoGrader(REPO_URL)

def submit_answer(problem_id: str, answer: Any, lab_name: str = "test1"):
    """
    답안 제출 함수 - 학생들이 사용할 함수
    
    Args:
        problem_id: 문제 ID (예: "problem_1")
        answer: 학생 답안
        lab_name: 실습 이름 (예: "test1", "test2", "midterm")
    """
    answer_file = f"{lab_name}/answers.json"
    result = grader.check_answer(problem_id, answer, answer_file)
    
    # 결과 출력
    print("=" * 40)
    print(f"📝 {lab_name.upper()} - 문제 {result['problem_id']}")
    print(f"📊 결과: {'✅ 정답' if result['correct'] else '❌ 오답'}")
    print(f"💬 {result['feedback']}")
    if not result['correct'] and result['expected'] != "정답 비공개":
        print(f"🔍 참고: {result['expected']}")
    print("=" * 40)
    
    return result

def create_lab_functions(lab_name: str, num_problems: int):
    """
    특정 실습용 채점 함수들을 동적으로 생성
    
    Args:
        lab_name: 실습 이름 (예: "test1", "midterm")
        num_problems: 문제 개수
    """
    # 전역 네임스페이스에 함수들을 추가
    globals_dict = globals()
    
    for i in range(1, num_problems + 1):
        problem_id = f"problem_{i}"
        
        # 동적으로 함수 생성
        def make_check_function(pid, lab):
            def check_function(student_answer):
                return submit_answer(pid, student_answer, lab)
            return check_function
        
        # 함수를 전역 네임스페이스에 추가
        func_name = f"check_problem_{i}"
        globals_dict[func_name] = make_check_function(problem_id, lab_name)

# 사용법을 출력하는 함수
def show_usage():
    """사용법 안내"""
    print("🎯 채점 시스템 사용법:")
    print("1. create_lab_functions('실습명', 문제개수) 호출")
    print("2. 문제 해결 후 check_problem_X(답안) 호출")
    print("\n📚 예시:")
    print("create_lab_functions('test1', 2)  # test1 실습, 2문제")
    print("check_problem_1(answer1)         # 문제 1 채점")
    print("check_problem_2(answer2)         # 문제 2 채점")

print("✅ 스마트 채점 시스템이 로드되었습니다!")
show_usage()
