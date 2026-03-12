import os
from PIL import Image

def process_images():
    base_dir = 'images'  # 원본 폴더
    thumb_root = os.path.join(base_dir, 'thumbnails') # 썸네일 저장 경로
    
    # 변환할 확장자 목록
    target_extensions = ('.jpg', '.jpeg', '.png')

    # 썸네일 폴더가 없으면 생성
    if not os.path.exists(thumb_root):
        os.makedirs(thumb_root)

    # images 폴더 순회
    for root, dirs, files in os.walk(base_dir):
        # 썸네일 폴더 자체는 건너뜀
        if 'thumbnails' in root:
            continue

        for filename in files:
            if filename.lower().endswith(target_extensions):
                # 파일 경로 설정
                file_path = os.path.join(root, filename)
                relative_path = os.path.relpath(root, base_dir)
                
                # 썸네일 저장용 하위 폴더 생성 (normal, rare 등 구조 유지)
                target_thumb_dir = os.path.join(thumb_root, relative_path)
                if not os.path.exists(target_thumb_dir):
                    os.makedirs(target_thumb_dir)

                # 파일명 변경 (확장자 .webp로)
                name_no_ext = os.path.splitext(filename)[0]
                webp_name = f"{name_no_ext}.webp"
                
                with Image.open(file_path) as img:
                    # 1. 원본을 고화질 WebP로 변환하여 같은 위치에 저장
                    # (기존 jpg를 대체하려면 나중에 삭제 코드를 넣으세요)
                    dest_path = os.path.join(root, webp_name)
                    img.save(dest_path, 'WEBP', quality=85)
                    print(f"[원본 변환] {dest_path}")

                    # 2. 썸네일 생성 (가로 300px 기준, 비율 유지)
                    thumb_img = img.copy()
                    thumb_img.thumbnail((300, 300)) # 최대 크기 300px 제한
                    
                    thumb_path = os.path.join(target_thumb_dir, webp_name)
                    # 저용량 설정을 위해 quality를 낮춤 (50~60 권장)
                    thumb_img.save(thumb_path, 'WEBP', quality=60)
                    print(f"[썸네일 생성] {thumb_path}")

    print("\n✅ 모든 작업이 완료되었습니다!")

if __name__ == "__main__":
    process_images()