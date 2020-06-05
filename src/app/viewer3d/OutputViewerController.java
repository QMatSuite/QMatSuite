package app.viewer3d;

import java.awt.Desktop;
import java.io.File;
import java.io.IOException;
import java.net.URL;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.ResourceBundle;
import java.util.Scanner;
import java.util.stream.Collectors;
import java.util.stream.Stream;

import com.consts.Constants.EnumCard;
import com.consts.Constants.EnumNameList;

import javafx.fxml.FXML;
import javafx.fxml.Initializable;
import javafx.scene.control.Button;
import javafx.scene.control.ListCell;
import javafx.scene.control.ListView;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import javafx.scene.paint.Color;
import javafx.scene.text.Text;
import javafx.scene.text.TextFlow;
import javafx.util.Callback;
import main.MainClass;

public class OutputViewerController implements Initializable{

    @FXML private HBox rootHbox;

    @FXML private VBox vBoxCalcFolder,vboxFiles,vboxMainPlot;

    @FXML private ListView<String> listCalcFolders;

    @FXML private ListView<String> listFiles;
    
    @FXML private TextFlow textFlowDisplay;
    
    @FXML private Button deleteFolderButton,deleteFileButton,openAsButton;
    
    private MainClass mainClass;
    
    private File calcFolder;
    
    private File inoutFiles;
    
    public OutputViewerController(MainClass mc) {
    	mainClass = mc;
	}

	@Override
	public void initialize(URL arg0, ResourceBundle arg1) {
		listCalcFolders.getSelectionModel().selectedItemProperty().addListener((ov, oldTab, newTab) -> {
			if(newTab==null || newTab.isEmpty()) return;
			File pjFolder = getProjectFolder();
			if(pjFolder==null || !pjFolder.canRead()) return;
			calcFolder = new File(pjFolder,newTab);
			if(calcFolder==null || !calcFolder.canRead() || !calcFolder.isDirectory()) return;
			
			listFiles.getItems().clear();
			
			File[] fileList = calcFolder.listFiles();
			for (File f : fileList) {
				listFiles.getItems().add(f.getName());
			}
		});
		listFiles.getSelectionModel().selectedItemProperty().addListener((ov, oldTab, newTab) -> {
			if(newTab==null || newTab.isEmpty()) return;
			if(calcFolder==null || !calcFolder.canRead() || !calcFolder.isDirectory()) return;
			inoutFiles = new File(calcFolder,newTab);
			
			if(inoutFiles==null || !inoutFiles.canRead()) return;
			if(inoutFiles.isDirectory()) {
				textFlowDisplay.getChildren().clear();
				textFlowDisplay.getChildren().add(new Text("Target file is a directory."));}
			else {
				readTextFileToTextFlow(inoutFiles);
			}
		});
		openAsButton.setOnAction((event) -> {
			if(inoutFiles==null || !inoutFiles.canRead()) return;
			try {
				Desktop.getDesktop().open(inoutFiles);
			} catch (IOException e) {
				// TODO Auto-generated catch block
				e.printStackTrace();
			}
		});
		
	}
	private void readTextFileToTextFlow(File inoutFiles) {
		try {
//			String data = new String(Files.readAllBytes(inoutFiles.toPath()));
			textFlowDisplay.getChildren().clear();
//			textFlowDisplay.getChildren().add(new Text(data));
		    Scanner sc = new Scanner(inoutFiles); 
		  
		    String strTmp;
		    Text txtTmp;
		    int lineCount=0;
		    while (sc.hasNextLine()) {
		    	lineCount++;
		    	strTmp = sc.nextLine();
		    	txtTmp = new Text(strTmp+"\n");
		    	if(strTmp!=null && strTmp.contains("calculation")) {txtTmp.setFill(Color.BLUE);}
		    	if(strTmp!=null && containsSectionName(strTmp)) {txtTmp.setFill(Color.GREEN);}
		    	textFlowDisplay.getChildren().add(txtTmp);
		    }
		    if(lineCount==0) {
		    	textFlowDisplay.getChildren().add(new Text("No lines detected. File empty or binary file."));
		    }
		} catch (IOException e) {
			e.printStackTrace();
		} 
	}
	private boolean containsSectionName(String stTmp) {
		if(stTmp==null || stTmp.isEmpty()) return false;
		String newstTmp = stTmp.replaceAll("\\s+","").toLowerCase();//remove all whitespaces and to lower case
		List<String> enumValues1 = Stream.of(EnumNameList.values())
                .map(EnumNameList::toString)
                .collect(Collectors.toList());
		List<String> enumValues2 = Stream.of(EnumCard.values())
                .map(EnumCard::toString)
                .collect(Collectors.toList());
		for (String st : enumValues1) {
			if(newstTmp.contains(st.trim().toLowerCase())) {return true;}
		}
		for (String st : enumValues2) {
			if(newstTmp.contains(st.trim().toLowerCase())) {return true;}
		}
		return false;
		
	}
	private File getProjectFolder() {
		String wsp = mainClass.projectManager.workSpacePath;
		String pj = mainClass.projectManager.getActiveProjectName();
		if(wsp==null || pj==null || pj.isEmpty()) return null;
		return new File(new File(wsp),pj);
	}
	public void updateProjectFolder() {
		File pjFolder = getProjectFolder();
		if(pjFolder==null || !pjFolder.canRead()) return;

		listCalcFolders.getItems().clear();listFiles.getItems().clear();
		
		File[] fileList = pjFolder.listFiles();
		int count = 0;
		for (File f : fileList) {
			if(f.isDirectory()) {listCalcFolders.getItems().add(f.getName());count++;}
		}
		ArrayList<String> pureFiles = new ArrayList<String>();
		for (File f : fileList) {
			if(f.isFile()) {listCalcFolders.getItems().add(f.getName());pureFiles.add(f.getName());}
		}
		if(count>0) {listCalcFolders.getSelectionModel().select(0);}
		listCalcFolders.setCellFactory(new Callback<ListView<String>, ListCell<String>>() {
	        @Override 
	        public ListCell<String> call(ListView<String> param) {
	            return new ListCell<String>() {
	                @Override 
	                protected void updateItem(String item, boolean empty) {
	                    super.updateItem(item, empty);
	                    if (pureFiles.contains(item)) {
	                        setDisable(true);setTextFill(Color.LIGHTGRAY);
	                    } else {
	                        setDisable(false);setTextFill(Color.BLACK);
	                    }
	                    setText(item);
	                }

	            };
	        }
	    });
		
	}


}
