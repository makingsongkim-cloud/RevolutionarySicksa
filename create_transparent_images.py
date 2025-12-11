#!/usr/bin/env python3
"""
밥상 이미지를 투명 배경으로 변환하고 뒷면에 글자를 추가하는 스크립트
"""

from PIL import Image, ImageDraw, ImageFont
import os

def make_circular_transparent(input_path, output_path, size=(900, 900)):
    """
    원형 이미지를 만들고 배경을 단색으로 채움 (체커보드 제거)
    """
    # 이미지 열기
    img = Image.open(input_path).convert("RGBA")
    
    # 이미지 크기 조정
    img = img.resize(size, Image.Resampling.LANCZOS)
    
    # 단색 배경 생성 (웹 배경색과 동일: #E0E0E0)
    output = Image.new('RGB', size, (224, 224, 224))  # #E0E0E0
    
    # 원형 마스크 생성
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)
    
    # RGBA를 RGB로 변환 (배경색과 합성)
    if img.mode == 'RGBA':
        # 알파 채널 추출
        background = Image.new('RGB', size, (224, 224, 224))
        background.paste(img, (0, 0), img)
        img = background
    
    # 마스크 적용하여 원형으로 자르기
    output.paste(img, (0, 0), mask)
    
    # 저장
    output.save(output_path, 'PNG')
    print(f"✅ 단색 배경 이미지 생성 완료: {output_path}")

def create_back_with_text(output_path, text="오늘의 점심", size=(900, 900)):
    """
    밥상 뒷면 이미지 생성 (단색 배경 + 텍스트 - 십자가 제거)
    """
    # 단색 배경 생성 (웹 배경색과 동일: #E0E0E0)
    img = Image.new('RGB', size, (224, 224, 224))
    draw = ImageDraw.Draw(img)
    
    # 원형 테이블 밑면 그리기 (어두운 갈색) - 지지대 없이 깔끔하게
    draw.ellipse((0, 0, size[0], size[1]), fill=(101, 67, 33))
    
    # 중앙에 작은 원형 마크 (테이블 중심점 표시)
    center_x, center_y = size[0] // 2, size[1] // 2
    mark_radius = 30
    draw.ellipse(
        (center_x - mark_radius, center_y - mark_radius,
         center_x + mark_radius, center_y + mark_radius),
        fill=(70, 40, 20)
    )
    
    # 폰트 설정 (시스템 한글 폰트 사용)
    try:
        # macOS 한글 폰트
        font = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 120)
    except:
        try:
            # 다른 한글 폰트 시도
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/AppleGothic.ttf", 120)
        except:
            # 기본 폰트 사용
            font = ImageFont.load_default()
    
    # 텍스트 크기 계산
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # 텍스트 위치 (중앙)
    text_x = (size[0] - text_width) // 2
    text_y = (size[1] - text_height) // 2
    
    # 텍스트 외곽선 (검은색, 더 두껍게)
    outline_width = 8
    for adj_x in range(-outline_width, outline_width+1):
        for adj_y in range(-outline_width, outline_width+1):
            draw.text((text_x + adj_x, text_y + adj_y), text, font=font, fill=(0, 0, 0))
    
    # 텍스트 본체 (흰색)
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255))
    
    # 저장
    img.save(output_path, 'PNG')
    print(f"✅ 뒷면 이미지 생성 완료: {output_path}")

if __name__ == "__main__":
    # 현재 디렉토리 확인
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"작업 디렉토리: {current_dir}")
    
    # 앞면 이미지 (음식 차려진 밥상) - 투명 배경으로 변환
    front_input = os.path.join(current_dir, "table_front.png")
    front_output = os.path.join(current_dir, "table_front_transparent.png")
    
    if os.path.exists(front_input):
        make_circular_transparent(front_input, front_output)
    else:
        print(f"❌ 입력 파일을 찾을 수 없습니다: {front_input}")
    
    # 뒷면 이미지 생성
    back_output = os.path.join(current_dir, "table_back_transparent.png")
    create_back_with_text(back_output)
    
    print("\n🎉 모든 이미지 생성 완료!")
