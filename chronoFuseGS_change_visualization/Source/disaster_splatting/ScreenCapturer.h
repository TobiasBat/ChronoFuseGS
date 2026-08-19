#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ScreenCapturer.generated.h"

UCLASS()
class DISASTER_SPLATTING_API AScreenCapturer : public AActor
{
	GENERATED_BODY()
	
public:    
	AScreenCapturer();
	int FallBackWidth;
	int FallBackHeight;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Capture")
	FDirectoryPath SavePath;
	
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Capture")
	USceneCaptureComponent2D* CaptureComponent;

	UFUNCTION(BlueprintCallable, Category = "Capture")
	void TakeScreenshot(FString FileName);

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Capture")
	TArray<int> CaptureSequenceCamerasIndex;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Capture")
	TArray<float> AllTime4Combinations;  

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Capture")
	TArray<float> AllTime3Combinations;  

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Capture")
	int NumT; 
	
	UFUNCTION(BlueprintCallable, Category = "Capture")
	void CaptureAllTimeCombinations();

	UFUNCTION(BlueprintCallable, Category = "Capture")
	TArray<float> GetTimeCombination(int Index);
	
	
	virtual void BeginPlay() override;
protected:
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	
private:
	FTimerHandle TimerHandle_AllTimeCapture;
	int AllTmeCapturingIndex = 0; 
	bool bRTInitialized = false;
	FDelegateHandle ViewportResizedHandle;
	FString PendingFileName;
	FTimerHandle CaptureTimerHandle;
	
	UPROPERTY(Transient)
	UTextureRenderTarget2D* StaticRT;

	void SyncShowFlagsFromViewport() const;
	void RescaleRTToCurrentScreenPercentage() const;
	void InitRT();
	void TryInitializeRT();
	void OnViewportResized(FViewport* Viewport, uint32);

	void CaptureAllTimeRec(); 
};